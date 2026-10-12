#!/usr/bin/env python3
"""V0.5.82: audit same-raw-ID jumps in gate-visible trace data, offline.

This is a diagnostic, never a scoring or event-mutation utility. It cannot
prove the absence of jumps outside the finite-gate track sampling window.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from math import hypot
from pathlib import Path
from zipfile import ZipFile

DEFAULT_LIMIT = 0.18


def box_diagonal(rect) -> float:
    return hypot(max(0.0, float(rect[2]) - float(rect[0])),
                 max(0.0, float(rect[3]) - float(rect[1])))


def jump_record(previous: dict, current: dict, width: float, height: float, limit: float) -> dict | None:
    try:
        gap = int(current['frame_index']) - int(previous['frame_index'])
        if not (0 < gap <= 3):
            return None
        a, b = previous['center'], current['center']
        prior_box, box = previous['rect'], current['rect']
        distance = hypot(float(b[0]) - float(a[0]), float(b[1]) - float(a[1]))
        diag = max(1.0, hypot(width, height))
        threshold = max(diag * limit, 3.0 * max(box_diagonal(prior_box), box_diagonal(box), 1.0))
        if distance <= threshold:
            return None
        return {
            'raw_track_id': int(current['raw_track_id']),
            'canonical_before': int(previous['track_id']),
            'canonical_after': int(current['track_id']),
            'source_frame_index': int(current['frame_index']),
            'source_time_seconds': round(float(current['source_time_seconds']), 3),
            'gap_frames': gap,
            'distance_pixels': round(distance, 3),
            'distance_frame_diagonal_ratio': round(distance / diag, 6),
            'threshold_pixels': round(threshold, 3),
        }
    except (TypeError, ValueError, KeyError, IndexError):
        return None


def inspect_zip(path: Path, limit: float = DEFAULT_LIMIT) -> dict:
    if not 0 <= limit <= 1:
        raise ValueError('Raw ID jump limit must be between zero and one.')
    with ZipFile(path, 'r') as archive:
        members = set(archive.namelist())
        for name in ('manifest.json', 'benchmark-trace.jsonl.gz', 'events.json'):
            if name not in members:
                raise ValueError(f'Missing benchmark evidence: {name}')
        manifest = json.loads(archive.read('manifest.json'))
        trace_meta = manifest.get('trace') or {}
        if not trace_meta.get('available') or not trace_meta.get('closed'):
            raise ValueError('Benchmark trace missing or incomplete; cannot audit.')
        if archive.getinfo('benchmark-trace.jsonl.gz').file_size > 134217728:
            raise ValueError('Compressed trace exceeds the 128 MB audit safety limit.')
        h = hashlib.sha256()
        with archive.open('benchmark-trace.jsonl.gz') as f:
            while chunk := f.read(1024 * 1024):
                h.update(chunk)
        if h.hexdigest() != trace_meta.get('compressed_sha256'):
            raise ValueError('Compressed trace SHA-256 verification failed.')
        last = {}
        flagged = []
        counted_frames = 0
        seen_geometry = False
        width = height = 0.0
        with gzip.open(archive.open('benchmark-trace.jsonl.gz'), 'rt', encoding='utf-8') as f:
            for line in f:
                obj = json.loads(line)
                if obj.get('kind') == 'geometry_metadata':
                    width = float(obj.get('frame_width', 0))
                    height = float(obj.get('frame_height', 0))
                    seen_geometry = width > 0 and height > 0
                    continue
                if obj.get('kind') or 'frame_index' not in obj:
                    continue
                if not seen_geometry:
                    raise ValueError('Frame evidence arrived without geometry metadata.')
                counted_frames += 1
                for row in obj.get('gate_tracks') or []:
                    raw_id = row.get('raw_track_id')
                    if raw_id is None or row.get('center') is None or row.get('rect') is None:
                        continue
                    try:
                        raw_id = int(raw_id)
                    except (TypeError, ValueError):
                        continue
                    now = {
                        'raw_track_id': raw_id, 'track_id': row['track_id'],
                        'center': row['center'], 'rect': row['rect'],
                        'frame_index': obj['frame_index'],
                        'source_time_seconds': obj.get('source_time_seconds', 0.0),
                    }
                    prior = last.get(raw_id)
                    if prior:
                        incident = jump_record(prior, now, width, height, limit)
                        if incident is not None:
                            flagged.append(incident)
                    last[raw_id] = now
        if counted_frames == 0:
            raise ValueError('Trace has no frame records.')
        events = json.loads(archive.read('events.json'))
        for incident in flagged:
            timecode = incident['source_time_seconds']
            incident['nearby_persisted_events'] = [
                {'event_id': e.get('id'), 'time': e.get('source_time_seconds'),
                 'method': e.get('crossing_method'), 'direction': e.get('direction')}
                for e in events
                if isinstance(e.get('source_time_seconds'), (float, int))
                and abs(e['source_time_seconds'] - timecode) <= 1.0
            ]
        return {
            'schema_version': 1, 'version': '0.5.82',
            'session_id': manifest.get('session_id'),
            'benchmark_id': manifest.get('benchmark_id'),
            'scope': 'gate_tracks visible in trace only (not all detections)',
            'raw_id_jump_ratio': limit,
            'frame_count': counted_frames,
            'raw_ids_seen_near_gate': len(last),
            'flagged_discontinuities': len(flagged),
            'incidents': flagged,
            'warning': ('This is a read-only candidate audit. Neither GT nor AI events are changed. '
                        'Zero flagged gate-visible jumps does NOT prove that the AI is accurate.'),
        }


def write_report(data: dict, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / 'raw-id-audit.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# Traffic AI V0.5.82 - Raw ID Continuity Audit', '',
        f"- Session: **{data['session_id']}** / Benchmark: **{data['benchmark_id']}**",
        f"- Frames audited: **{data['frame_count']}**",
        f"- Raw IDs visible near gate: **{data['raw_ids_seen_near_gate']}**",
        f"- Large near-instant same-raw discontinuities: **{data['flagged_discontinuities']}**",
        f"- Scope: {data['scope']}",
        '', data['warning'], '',
    ]
    for row in data['incidents']:
        lines.append(f"- **{row['source_time_seconds']:.3f}s** raw={row['raw_track_id']}, "
                     f"gap={row['gap_frames']} frames, {row['distance_pixels']} px. "
                     f"Nearby DB events: {len(row['nearby_persisted_events'])}.")
    (dest / 'raw-id-audit.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export-zip', type=Path, required=True)
    parser.add_argument('--output-directory', type=Path, required=True)
    parser.add_argument('--raw-id-jump-ratio', type=float, default=DEFAULT_LIMIT)
    args = parser.parse_args()
    try:
        data = inspect_zip(args.export_zip, args.raw_id_jump_ratio)
        write_report(data, args.output_directory)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.exit(2, f'[FAIL] Raw ID audit: {exc}\n')
    print(f"[OK] Session #{data['session_id']}, {data['frame_count']} frames; "
          f"{data['flagged_discontinuities']} gate-visible discontinuities. ")
    print(f"Report: {args.output_directory / 'raw-id-audit.md'}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
