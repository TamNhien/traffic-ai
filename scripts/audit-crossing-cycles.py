#!/usr/bin/env python3
"""V0.5.92 verified, read-only same-canonical-ID crossing-cycle evidence audit.

A canonical tracker token does NOT prove physical vehicle identity. Opposite
crossings can be legitimate repeated passages. Never suppress persisted events,
edit GT, or claim a Precision/F1 gain based on this report.
"""
from __future__ import annotations

import argparse
import csv
import gzip
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
import io
import json
import math
from pathlib import Path
import sys
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent


def _load_verify():
    spec = spec_from_file_location('traffic_compare_for_cycle_audit', HERE / 'compare-benchmark-exports.py')
    if spec is None or spec.loader is None:
        raise ValueError('Benchmark verifier unavailable')
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def event_seconds(event: dict) -> float:
    value = event.get('source_time_seconds')
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
        raise ValueError('Invalid event source_time_seconds')
    return float(value)


def _tracks_at_crossings(archive: Path, manifest: dict, frame_indices: set[int]) -> dict[int, dict]:
    """One-pass trace witnesses; no GT inference, no 200MB uncompressed buffer."""
    if not frame_indices:
        return {}
    trace = manifest.get('trace') or {}
    if not trace.get('closed') or not trace.get('available'):
        raise ValueError('Trace must be closed and available')
    candidates = {i + delta for i in frame_indices for delta in range(-2, 4) if i + delta > 0}
    witnesses: dict[int, dict] = {}
    with ZipFile(archive) as z:
        name = 'benchmark-trace.jsonl.gz' if 'benchmark-trace.jsonl.gz' in z.namelist() else 'benchmark-trace.jsonl'
        with z.open(name) as raw:
            reader = gzip.GzipFile(fileobj=raw) if name.endswith('.gz') else raw
            digest = sha256()
            length = 0
            has_metadata = False
            has_footer = False
            for line in reader:
                digest.update(line)
                length += len(line)
                # Zip was integrity-checked before decompression; still reject
                # a forged original source length/digest or incomplete footer.
                if length > 512 * 1024 * 1024:
                    raise ValueError('Uncompressed trace exceeds safety limit')
                if b'"kind":"session_metadata"' in line:
                    has_metadata = True
                if b'"kind":"delivery_summary"' in line or b'"kind":"session_summary"' in line:
                    has_footer = True
                if b'"gate_tracks"' not in line:
                    continue
                row = json.loads(line)
                frame = row.get('frame_index')
                if isinstance(frame, int) and frame in candidates:
                    tracks = row.get('gate_tracks')
                    if not isinstance(tracks, list):
                        raise ValueError('Malformed trace gate_tracks')
                    witnesses[frame] = {
                        int(t['track_id']): {
                            'raw_track_id': t.get('raw_track_id'),
                            'anchor_signed': t.get('anchor_signed'),
                            'rect': t.get('rect'),
                            'stitched': t.get('stitched'),
                        }
                        for t in tracks if isinstance(t, dict) and type(t.get('track_id')) is int
                    }
            expected_length = trace.get('source_bytes')
            expected_digest = trace.get('source_sha256')
            if expected_length is not None and length != expected_length:
                raise ValueError('Uncompressed trace length mismatch')
            if expected_digest is not None and digest.hexdigest() != expected_digest:
                raise ValueError('Uncompressed trace SHA-256 mismatch')
            # Some older synthetic traces do not carry the delivery footer; a
            # real export claims source_bytes and must also prove closure.
            if expected_length is not None and not (has_metadata and has_footer):
                raise ValueError('Trace session metadata/delivery footer missing')
    return witnesses


def _witness(witnesses: dict[int, dict], frame: int | None, track: int) -> dict:
    if type(frame) is not int:
        return {'frame': None, 'raw_track_id': None, 'anchor_signed': None, 'stitched': None}
    nearest = []
    for probe in range(frame - 2, frame + 4):
        witness = witnesses.get(probe, {}).get(track)
        if witness:
            nearest.append((abs(probe - frame), probe, witness))
    if not nearest:
        return {'frame': None, 'raw_track_id': None, 'anchor_signed': None, 'stitched': None}
    _distance, actual_frame, obj = min(nearest, key=lambda x: (x[0], x[1]))
    return {'frame': actual_frame, 'raw_track_id': obj['raw_track_id'],
            'anchor_signed': obj['anchor_signed'], 'stitched': obj['stitched']}


def build_audit(events: list[dict], false_positives: list[dict] | None = None,
                witnesses: dict[int, dict] | None = None, max_gap_seconds: float = 12.0) -> dict:
    if not 0 < max_gap_seconds <= 30 or not math.isfinite(max_gap_seconds):
        raise ValueError('max_gap_seconds must be within (0, 30]')
    if not isinstance(events, list) or not all(isinstance(e, dict) for e in events):
        raise ValueError('Invalid events list')
    seen = set()
    rows = []
    by_id: dict[int, list[dict]] = {}
    extra_ids = {fp['ai_event_id'] for fp in (false_positives or []) if type(fp.get('ai_event_id')) is int}
    for event in events:
        eid, tid = event.get('id'), event.get('tracking_id')
        t = event_seconds(event)
        if type(eid) is not int or type(tid) is not int or eid in seen:
            raise ValueError('Missing/duplicate event ID or canonical track ID')
        seen.add(eid)
        by_id.setdefault(tid, []).append(event)
    wit = witnesses or {}
    for track, group in by_id.items():
        group.sort(key=lambda event: (event_seconds(event), event['id']))
        for k, newer in enumerate(group):
            for older in reversed(group[:k]):
                gap = round(event_seconds(newer) - event_seconds(older), 6)
                if gap > max_gap_seconds:
                    break
                if gap < 0:
                    raise ValueError('Event chronology invalid')
                # Adjacent/nonadjacent same canonical token can be genuine two
                # passages; this is a review candidate, NOT a duplicate claim.
                older_w = _witness(wit, older.get('source_frame_index'), track)
                newer_w = _witness(wit, newer.get('source_frame_index'), track)
                old_raw, new_raw = older_w['raw_track_id'], newer_w['raw_track_id']
                if old_raw is not None and new_raw is not None:
                    provenance = 'same_raw_observed' if old_raw == new_raw else 'raw_alias_changed'
                else:
                    provenance = 'insufficient_frame_witness'
                rows.append({
                    'prior_ai_event_id': older['id'], 'current_ai_event_id': newer['id'],
                    'canonical_track_id': track, 'prior_time': event_seconds(older),
                    'current_time': event_seconds(newer), 'gap_seconds': gap,
                    'prior_direction': older.get('direction'), 'current_direction': newer.get('direction'),
                    'prior_method': older.get('crossing_method'), 'current_method': newer.get('crossing_method'),
                    'prior_extra': older['id'] in extra_ids, 'current_extra': newer['id'] in extra_ids,
                    'prior_raw_track_id': old_raw, 'current_raw_track_id': new_raw,
                    'prior_witness_frame': older_w['frame'], 'current_witness_frame': newer_w['frame'],
                    'raw_provenance': provenance, 'identity_proven': False,
                    'review_action': 'Xem clip: xác nhận xe quay đầu/cắt hai lần hay tracker nối nhầm; không tự trừ số.',
                })
    rows.sort(key=lambda r: (r['current_time'], r['prior_time'], r['current_ai_event_id']))
    return {
        'format': 'traffic-ai-crossing-cycle-audit', 'schema_version': 1,
        'events_total': len(events), 'max_gap_seconds': max_gap_seconds,
        'pairs_total': len(rows), 'pairs_with_unmatched_ai': sum(r['prior_extra'] or r['current_extra'] for r in rows),
        'raw_alias_changed_pairs': sum(r['raw_provenance'] == 'raw_alias_changed' for r in rows),
        'evidence_notice': 'Canonical/Raw IDs do not prove physical identity. Opposite IN/OUT can be valid repeated passages. No events or GT are changed.',
        'pairs': rows,
    }


def audit_archive(archive: Path, *, max_gap_seconds: float = 12.0) -> dict:
    data = _load_verify()._read_evidence(archive)
    events = data['events']
    frames = {e.get('source_frame_index') for e in events if type(e.get('source_frame_index')) is int}
    witnesses = _tracks_at_crossings(archive, data['manifest'], frames)
    report = data['report']
    result = build_audit(events, report.get('false_positive_items') if data['scored'] else [],
                         witnesses, max_gap_seconds=max_gap_seconds)
    result.update({
        'benchmark_id': report['benchmark']['id'], 'session_id': report['session_id'],
        'scoring_available': bool(data['scored']),
        'missed': report.get('missed') if data['scored'] else None,
        'extra': report.get('false_positives') if data['scored'] else None,
    })
    return result


def write_audit(result: dict, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest/'crossing-cycles.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    rows = result['pairs']
    columns = [
        'prior_ai_event_id','current_ai_event_id','canonical_track_id','prior_time','current_time',
        'gap_seconds','prior_direction','current_direction','prior_method','current_method',
        'prior_extra','current_extra','prior_raw_track_id','current_raw_track_id',
        'prior_witness_frame','current_witness_frame','raw_provenance','identity_proven','review_action',
    ]
    with (dest/'crossing-cycles.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    md = [f'# Kiểm tra chu kỳ qua vạch · Benchmark #{result.get("benchmark_id", "?")}', '',
          f'- {result["events_total"]} event AI; {result["pairs_total"]} cặp dùng chung canonical ID trong {result["max_gap_seconds"]:g} giây.',
          f'- {result["pairs_with_unmatched_ai"]} cặp có ít nhất một event AI chưa khớp GT.',
          f'- {result["raw_alias_changed_pairs"]} cặp có bằng chứng raw ID khác nhau ở khung hình gần event.',
          '- Không loại/trừ event hoặc tính lại F1 tự động.', '',
          '| Hai event AI | Thời gian (s) | Hướng | Track | Raw-ID evidence | GT dư? |',
          '|---|---:|---|---:|---|---|']
    for row in rows:
        md.append(f'| {row["prior_ai_event_id"]} → {row["current_ai_event_id"]} | '
                  f'{row["gap_seconds"]:.3f} | {row["prior_direction"]} → {row["current_direction"]} | '
                  f'{row["canonical_track_id"]} | {row["raw_provenance"]} | '
                  f'{"Có" if row["prior_extra"] or row["current_extra"] else "Không"} |')
    md += ['', '**Lưu ý:** Một xe quay lại cắt vạch được tính thêm lượt. Cùng ID không chứng minh cùng xe.', '']
    (dest/'crossing-cycles.md').write_text('\n'.join(md), encoding='utf8')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Verified read-only crossing-cycle evidence audit')
    parser.add_argument('--export', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--max-gap-seconds', type=float, default=12.0)
    args = parser.parse_args(argv)
    try:
        result = audit_archive(args.export, max_gap_seconds=args.max_gap_seconds)
        write_audit(result, args.output_dir)
        print(f'Benchmark #{result["benchmark_id"]} / Session #{result["session_id"]}: '
              f'AI {result["events_total"]}, {result["pairs_total"]} cặp; '
              f'{result["pairs_with_unmatched_ai"]} cặp có dư, raw đổi {result["raw_alias_changed_pairs"]}')
        print(f'Reports: {args.output_dir.resolve()}')
        return 0
    except (ValueError, OSError, KeyError, TypeError, EOFError) as exc:
        print(f'[ERROR] Crossing-cycle audit: {exc}', file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
