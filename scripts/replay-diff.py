#!/usr/bin/env python3
"""Traffic AI V0.5.75: cross-run crossing delivery audit, NOT a GT benchmark.

Compare two *closed* benchmark-trace JSONL/.jsonl.gz or benchmark ZIPs of the same clip.
Pair events by observed crossing time, position and direction, never by unstable
ByteTrack ID or DB event ID. Report replay drift and persistence-decision flips;
do not change counts or infer false positives without Ground Truth.

Standard-library only, suitable for Windows Python 3.10+.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
import gzip
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import sys
from zipfile import BadZipFile, ZipFile

MAX_LINE_BYTES = 2 * 1024 * 1024
MAX_RAW_BYTES = 512 * 1024 * 1024
MAX_ROWS = 2_000_000
MAX_EVENTS = 100_000
MAX_ZIP_TRACE_BYTES = 128 * 1024 * 1024
LARGE_COST = 1e6


class EvidenceError(ValueError):
    """The input is incomplete, inconsistent or an incompatible replay."""


@dataclass(frozen=True)
class Crossing:
    frame: int
    time: float
    x: float
    y: float
    direction: str
    vehicle: str
    method: str
    track_id: int
    outcome: str
    reason: str

    def display(self) -> dict:
        return {
            "frame": self.frame, "seconds": round(self.time, 4),
            "position": [round(self.x, 5), round(self.y, 5)],
            "direction": self.direction, "vehicle_type": self.vehicle,
            "method": self.method, "track_id": self.track_id,
            "outcome": self.outcome, "dedup_reason": self.reason or None,
        }


@dataclass
class Replay:
    session_id: int
    camera_id: int
    fps: float
    frames: int
    geometry: dict
    events: list[Crossing]


def _valid_number(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise EvidenceError(f"Missing/invalid {name}")
    result = float(value)
    if not isfinite(result):
        raise EvidenceError(f"Non-finite {name}")
    return result


@contextmanager
def _open_trace(path: Path):
    """Stream a raw trace or verified optional trace member of a benchmark ZIP."""
    if path.suffix.lower() != '.zip':
        opener = gzip.open if path.name.lower().endswith('.gz') else open
        with opener(path, 'rb') as stream:
            yield stream
        return
    try:
        with ZipFile(path) as archive:
            members = archive.namelist()
            if len(members) > 32 or len(set(members)) != len(members):
                raise EvidenceError('Unexpected/duplicated ZIP entries')
            candidates = [name for name in ('benchmark-trace.jsonl.gz', 'benchmark-trace.jsonl') if name in members]
            if len(candidates) != 1 or 'manifest.json' not in members:
                raise EvidenceError('Benchmark ZIP must include one benchmark trace and a manifest')
            filename = candidates[0]
            info = archive.getinfo(filename)
            if not 0 < info.file_size <= MAX_ZIP_TRACE_BYTES:
                raise EvidenceError('Benchmark trace exceeds the bounded ZIP export size')
            if archive.getinfo('manifest.json').file_size > 1_000_000:
                raise EvidenceError('Benchmark manifest is too large')
            manifest = json.loads(archive.read('manifest.json'))
            if not isinstance(manifest, dict) or manifest.get('format') != 'traffic-ai-benchmark-diagnostics' or manifest.get('schema_version') != 1:
                raise EvidenceError('Unrecognized benchmark ZIP format')
            record = (manifest.get('files') or {}).get(filename)
            if not isinstance(record, dict) or record.get('bytes') != info.file_size:
                raise EvidenceError('Benchmark trace manifest size mismatch')
            digest = sha256()
            with archive.open(filename) as stream:
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
            if record.get('sha256') != digest.hexdigest():
                raise EvidenceError('Benchmark trace failed SHA-256 validation')
            with archive.open(filename) as raw:
                if filename.endswith('.gz'):
                    with gzip.GzipFile(fileobj=raw, mode='rb') as decoded:
                        yield decoded
                else:
                    yield raw
    except (BadZipFile, KeyError, UnicodeError, ValueError) as exc:
        if isinstance(exc, EvidenceError):
            raise
        raise EvidenceError(f'Invalid benchmark ZIP: {exc}') from exc


def _read_rows(path: Path):
    try:
        with _open_trace(path) as handle:
            line_no = 0
            total_bytes = 0
            while True:
                line = handle.readline(MAX_LINE_BYTES + 1)
                if not line:
                    break
                line_no += 1
                total_bytes += len(line)
                if line_no > MAX_ROWS or total_bytes > MAX_RAW_BYTES:
                    raise EvidenceError(f'{path.name} exceeds the maximum verified trace size/rows')
                if len(line) > MAX_LINE_BYTES:
                    raise EvidenceError(f'{path.name} line {line_no} exceeds {MAX_LINE_BYTES} bytes')
                try:
                    row = json.loads(line)
                except (ValueError, UnicodeError) as exc:
                    raise EvidenceError(f'{path.name} has invalid JSON at line {line_no}') from exc
                if not isinstance(row, dict):
                    raise EvidenceError(f'{path.name} line {line_no} is not a JSON object')
                yield row
    except (OSError, EOFError) as exc:
        raise EvidenceError(f'Cannot read {path}: {exc}') from exc


def load_trace(path: Path) -> Replay:
    metadata = geometry = summary = None
    events: list[Crossing] = []
    observed_frames = 0
    final_frame = None
    for row in _read_rows(path):
        kind = row.get('kind')
        if kind == 'session_metadata':
            if metadata is not None:
                raise EvidenceError('Duplicate session_metadata')
            metadata = row
        elif kind == 'geometry_metadata':
            if geometry is not None:
                raise EvidenceError('Duplicate geometry_metadata')
            geometry = row
        elif kind == 'delivery_summary':
            if summary is not None:
                raise EvidenceError('Duplicate delivery_summary')
            summary = row
        elif kind == 'event_delivery':
            if len(events) >= MAX_EVENTS:
                raise EvidenceError(f'Too many event_delivery records (>{MAX_EVENTS})')
            if row.get('stage') != 'backend_acknowledged' or row.get('outcome') not in {'created', 'deduplicated'}:
                raise EvidenceError('Event missing backend acknowledgement or valid outcome')
            x = _valid_number(row.get('crossing_x'), 'crossing_x')
            y = _valid_number(row.get('crossing_y'), 'crossing_y')
            time = _valid_number(row.get('source_time_seconds'), 'source_time_seconds')
            if not (0 <= x <= 1 and 0 <= y <= 1 and time >= 0):
                raise EvidenceError('Crossing time/position out of range')
            try:
                frame = int(row['source_frame_index'])
                track_id = int(row['tracking_id'])
            except (KeyError, ValueError, TypeError) as exc:
                raise EvidenceError('Invalid crossing frame/track ID') from exc
            if frame < 1 or row['source_frame_index'] != frame:
                raise EvidenceError('Invalid crossing frame')
            direction = str(row.get('direction', '')).lower()
            if direction not in ('in', 'out'):
                raise EvidenceError('Invalid crossing direction')
            events.append(Crossing(
                frame, time, x, y, direction,
                str(row.get('vehicle_type', '')), str(row.get('crossing_method') or ''),
                track_id, row['outcome'], str(row.get('dedup_reason') or ''),
            ))
        elif kind is None:
            observed_frames += 1
            if row.get('frame_index') != observed_frames:
                raise EvidenceError(f'Missing or duplicate frame near {observed_frames}')
            final_frame = row.get('frame_index')
        else:
            raise EvidenceError(f'Unexpected trace record kind {kind!r}')
    if metadata is None or geometry is None or summary is None:
        raise EvidenceError('Trace is incomplete: metadata, geometry and delivery summary are required')
    if not summary.get('delivery_drain_complete') or summary.get('pending_events') != 0 or summary.get('delivery_audit_dropped') != 0:
        raise EvidenceError('Unresolved or dropped event deliveries: replay comparison is unsafe')
    try:
        session_id = int(metadata['session_id'])
        camera_id = int(metadata['camera_id'])
        frames = int(metadata['source_frame_count'])
        fps = _valid_number(metadata['source_fps'], 'source_fps')
    except (KeyError, ValueError, TypeError) as exc:
        raise EvidenceError('Missing session metadata') from exc
    if fps <= 0 or frames < 1 or observed_frames != frames or final_frame != frames:
        raise EvidenceError(f'Incomplete frame stream: observed {observed_frames}, declared {frames}, final {final_frame}')
    for obj in (geometry, summary):
        if obj.get('session_id') != session_id or obj.get('camera_id') != camera_id:
            raise EvidenceError('Session/camera identity differs inside trace')
    if any(row.frame > frames or row.time > frames / fps + 1.0 for row in events):
        raise EvidenceError('Event time/frame outside clip')
    if not geometry.get('line') or not geometry.get('road_zone'):
        raise EvidenceError('Missing gate/Road Zone geometry')
    return Replay(session_id, camera_id, fps, frames, geometry, events)


def _geometry_signature(metadata: dict) -> str:
    # Ignore source session ID and camera ID; compare source dimensions + zones.
    keys = ('coordinate_system', 'frame_width', 'frame_height',
            'source_frame_width', 'source_frame_height', 'line', 'road_zone')
    return json.dumps({k: metadata.get(k) for k in keys}, sort_keys=True, separators=(',', ':'))


def check_compatible(previous: Replay, current: Replay) -> None:
    if previous.camera_id != current.camera_id:
        raise EvidenceError('Camera ID differs; choose replays of the same camera')
    if previous.session_id == current.session_id:
        raise EvidenceError('Both traces refer to the same session; choose two independent replays')
    if previous.fps != current.fps or previous.frames != current.frames:
        raise EvidenceError('FPS/length differs: cannot compare different source clips')
    if _geometry_signature(previous.geometry) != _geometry_signature(current.geometry):
        raise EvidenceError('Gate/Road Zone geometry differs; cannot attribute drift to AI')
    # The recorded metadata lacks video content hash; matching FPS/geometry/length
    # alone CANNOT prove these are the same physical video. Report this caveat.


def _hungarian(costs: list[list[float]]) -> list[tuple[int, int]]:
    """Rectangular minimum-cost assignment (rows <= columns), no dependencies."""
    n = len(costs)
    if not n:
        return []
    m = len(costs[0])
    if m < n or any(len(row) != m for row in costs):
        raise ValueError('Invalid assignment matrix')
    u = [0.0] * (n + 1)
    v = [0.0] * (m + 1)
    p = [0] * (m + 1)
    way = [0] * (m + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [float('inf')] * (m + 1)
        used = [False] * (m + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = float('inf')
            j1 = 0
            for j in range(1, m + 1):
                if used[j]:
                    continue
                cur = costs[i0 - 1][j - 1] - u[i0] - v[j]
                if cur < minv[j]:
                    minv[j] = cur
                    way[j] = j0
                if minv[j] < delta:
                    delta, j1 = minv[j], j
            for j in range(m + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    return [(p[j] - 1, j - 1) for j in range(1, m + 1) if p[j]]


def pair_crossings(before: list[Crossing], after: list[Crossing], time_window: float, distance_window: float):
    """One-to-one max-cardinality then min-cost pairing; no track-ID dependency."""
    if not before or not after:
        return [], list(before), list(after)
    # Only O(N^2) for short event lists, not for millions of frame detections.
    if max(len(before), len(after)) > 800:
        raise EvidenceError('Too many crossing events for safe quadratic comparison; split the clip')
    costs = []
    for a in before:
        row = []
        for b in after:
            distance = ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5
            offset = abs(a.time - b.time)
            if a.direction != b.direction or distance > distance_window or offset > time_window:
                row.append(LARGE_COST)
            else:
                # Approximate match only; dense multi-lane traffic may be ambiguous.
                row.append(offset / time_window + distance / distance_window +
                           (0.05 if a.vehicle != b.vehicle else 0.0))
        row.extend([4.0] * len(before))  # dummy destinations: unmatched previous
        costs.append(row)
    assignment = _hungarian(costs)
    matched = [(before[i], after[j]) for i, j in assignment if j < len(after) and costs[i][j] < 4.0]
    # Duplicate identical event records are rare but possible: use unique indices
    # to preserve multiplicity (dataclass identity/equality alone loses duplicates).
    used_b = Counter(a for a, _ in matched)
    used_c = Counter(b for _, b in matched)
    removed = []
    introduced = []
    for a in before:
        if used_b[a]:used_b[a]-=1
        else:removed.append(a)
    for b in after:
        if used_c[b]:used_c[b]-=1
        else:introduced.append(b)
    return matched, removed, introduced


def summarize(previous: Replay, current: Replay, time_window=0.75, distance_window=0.025) -> dict:
    check_compatible(previous, current)
    if time_window <= 0 or distance_window <= 0:
        raise EvidenceError('Matching windows must be positive')
    a = previous.events
    b = current.events
    pairs, removed, introduced = pair_crossings(a, b, time_window, distance_window)
    decisions = []
    shifts = []
    for old, new in pairs:
        if old.outcome != new.outcome or old.reason != new.reason:
            decisions.append({"before": old.display(), "after": new.display()})
        delta = new.time - old.time
        if abs(delta) > (2.0 / previous.fps):
            shifts.append({"before": old.display(), "after": new.display(), "shift_seconds": round(delta, 4)})
    created_a = [x for x in a if x.outcome == 'created']
    created_b = [x for x in b if x.outcome == 'created']
    persisted, removed_created, introduced_created = pair_crossings(created_a, created_b, time_window, distance_window)
    return {
        "format": "traffic-ai-replay-diff", "schema_version": 1,
        "analysis_type": "cross-run-consistency-not-ground-truth",
        "warning": ("Replay pairs are time/position/direction candidates, not proven physical vehicle IDs. "
                    "Trace metadata has no clip SHA-256; verify that the videos are identical. "
                    "Only a complete Ground Truth benchmark can determine missed/extra counts."),
        "previous": {"session": previous.session_id, "proposals": len(a), "created": len(created_a),
                     "deduplicated": len(a) - len(created_a)},
        "current": {"session": current.session_id, "proposals": len(b), "created": len(created_b),
                    "deduplicated": len(b) - len(created_b)},
        "settings": {"time_window_seconds": time_window, "distance_window_normalized": distance_window,
                     "fps": previous.fps, "frames": previous.frames},
        "summary": {"proposal_pairs": len(pairs), "proposal_removed": len(removed),
                    "proposal_introduced": len(introduced), "decision_changes": len(decisions),
                    "source_time_shifts_over_2_frames": len(shifts),
                    "created_pairs": len(persisted), "created_removed": len(removed_created),
                    "created_introduced": len(introduced_created),
                    "created_total_delta": len(created_b) - len(created_a)},
        "decision_changes": decisions,
        "source_time_shifts": shifts,
        "proposals_removed": [x.display() for x in removed],
        "proposals_introduced": [x.display() for x in introduced],
        "created_removed": [x.display() for x in removed_created],
        "created_introduced": [x.display() for x in introduced_created],
    }


def markdown_report(report: dict) -> str:
    s = report['summary']
    p, c = report['previous'], report['current']
    lines = [
        '# Traffic AI V0.5.75 — Replay Drift Audit', '',
        f"Session #{p['session']} → #{c['session']}", '',
        '> **Không phải điểm benchmark GT.** ' + report['warning'], '',
        '| Chỉ số | Lần trước | Lần sau |', '|---|---:|---:|',
        f"| Crossing đề xuất | {p['proposals']} | {c['proposals']} |",
        f"| Event được ghi | {p['created']} | {c['created']} |",
        f"| Event bị chống trùng | {p['deduplicated']} | {c['deduplicated']} |", '',
        '| Dấu hiệu biến động | Số lượt |', '|---|---:|',
    ]
    labels = [('proposal_pairs', 'Đề xuất ghép gần nhau'), ('proposal_removed', 'Đề xuất chỉ có lần trước'),
              ('proposal_introduced', 'Đề xuất chỉ có lần sau'), ('decision_changes', 'Đề xuất đổi quyết định'),
              ('created_pairs', 'Event ghi DB ghép gần nhau'), ('created_removed', 'Event DB chỉ có lần trước'),
              ('created_introduced', 'Event DB chỉ có lần sau'),
              ('source_time_shifts_over_2_frames', 'Đề xuất lệch timecode >2 frame')]
    lines += [f'| {label} | {s[key]} |' for key, label in labels]
    lines += ['', '## Sự kiện cần kiểm tra (timecode theo video)', '']
    for field, label in [('decision_changes', 'Đổi quyết định'), ('created_removed', 'Mất event DB so với lần trước'),
                         ('created_introduced', 'Event DB mới xuất hiện')]:
        lines += [f'### {label}', '']
        items = report[field]
        if not items:
            lines += ['Không có.', '']
            continue
        for record in items[:100]:
            if 'before' in record:
                old, new = record['before'], record['after']
                lines.append(f"- {old['seconds']:.3f}s → {new['seconds']:.3f}s · "
                             f"{old['outcome']} ({old['dedup_reason'] or '-'}) → "
                             f"{new['outcome']} ({new['dedup_reason'] or '-'})")
            else:
                lines.append(f"- {record['seconds']:.3f}s / frame {record['frame']} · "
                             f"{record['direction'].upper()} {record['vehicle_type']} · "
                             f"{record['method']} @ {record['position']}")
        if len(items) > 100:
            lines.append(f'- ... còn {len(items)-100} bản ghi trong JSON.')
        lines.append('')
    lines += ['## Kết luận có giới hạn', '',
              'Các chênh lệch nêu trên là **biến động giữa hai lượt phát lại**, '
              'không thể tự gán là GT lọt hoặc đếm dư. '
              'Để sửa thuật toán dựa trên bằng chứng, hãy xuất **Tải hồ sơ benchmark** '
              'cho đúng phiên đã chạy và đánh giá bằng `scripts/check-benchmark.ps1`.', '']
    return '\n'.join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description='Cross-replay event consistency audit; not a GT metric')
    p.add_argument('--previous', required=True, type=Path)
    p.add_argument('--current', required=True, type=Path)
    p.add_argument('--output-dir', default=Path('replay-diff-report'), type=Path)
    p.add_argument('--time-window', type=float, default=0.75)
    p.add_argument('--distance-window', type=float, default=0.025)
    p.add_argument('--strict', action='store_true', help='Fail if created set or persistence decisions differ')
    args = p.parse_args(argv)
    try:
        if args.previous.resolve() == args.current.resolve():
            raise EvidenceError('Previous and current file paths are identical')
        previous, current = load_trace(args.previous), load_trace(args.current)
        report = summarize(previous, current, args.time_window, args.distance_window)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / 'replay-diff.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (args.output_dir / 'replay-diff.md').write_text(markdown_report(report), encoding='utf-8')
        stats = report['summary']
        print(f"Session #{previous.session_id} → #{current.session_id}: "
              f"DB {report['previous']['created']} → {report['current']['created']}; "
              f"removed {stats['created_removed']}, introduced {stats['created_introduced']}, "
              f"decision flips {stats['decision_changes']}")
        print(f"Saved {args.output_dir / 'replay-diff.json'} and replay-diff.md")
        if args.strict and (stats['created_removed'] or stats['created_introduced'] or stats['decision_changes']):
            print('[FAIL] Replay persistence consistency gate', file=sys.stderr)
            return 1
        print('[PASS] Trace integrity/compatibility checks (not GT accuracy)')
        return 0
    except (EvidenceError, OSError, ValueError, TypeError) as exc:
        print(f'[ERROR] Replay evidence cannot be compared: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
