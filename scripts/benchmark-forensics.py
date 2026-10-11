#!/usr/bin/env python3
"""V0.5.77: verified GT-to-AI error forensics; read-only, no count correction.

Requires the full 'Tai ho so benchmark' ZIP (not camera JPG/trace RAR).
Cases remain the exact unmatched GT and AI rows from the backend's global
assignment. Nearby tracker evidence is a hypothesis, never a new GT mark.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import math
import re
import sys
from pathlib import Path
from zipfile import ZipFile

MAX_TRACE_SOURCE_BYTES = 512 * 1024 * 1024
FRAME_PATTERN = re.compile(rb'"frame_index"\s*:\s*(\d+)')
TRACE_FILES = ('benchmark-trace.jsonl.gz', 'benchmark-trace.jsonl')


def _verified_load(zip_path: Path) -> tuple[dict, dict]:
    spec = importlib.util.spec_from_file_location('traffic_benchmark_gate', Path(__file__).with_name('benchmark-gate.py'))
    if spec is None or spec.loader is None:
        raise ValueError('Cannot load the validated benchmark gate')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.load_evidence(zip_path)


def _time(case: dict) -> float:
    for field in ('time', 'source_time_seconds', 'ai_time'):
        value = case.get(field)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
            return float(value)
    raise ValueError('Benchmark report case without finite source time')


def _event_id(case: dict) -> int | None:
    val = case.get('ai_event_id')
    return int(val) if isinstance(val, int) and not isinstance(val, bool) else None


def _read_trace(archive: ZipFile, manifest: dict, cases: list[dict], margin: float) -> dict:
    """Verify both transport/source digests, then gather only nearby frame evidence."""
    name = next((n for n in TRACE_FILES if n in archive.namelist()), None)
    if name is None:
        return {'available': False, 'reason': manifest.get('trace', {}).get('reason', 'missing')}
    entry = manifest.get('files', {}).get(name)
    if not isinstance(entry, dict) or entry.get('bytes') != archive.getinfo(name).file_size:
        raise ValueError(f'Trace manifest length missing/mismatched: {name}')
    h = hashlib.sha256()
    with archive.open(name) as fp:
        while chunk := fp.read(1024 * 1024):
            h.update(chunk)
    if h.hexdigest() != entry.get('sha256'):
        raise ValueError('Trace SHA-256 mismatch: export corrupted')
    if archive.getinfo(name).file_size > (128 * 1024 * 1024 if name.endswith(".gz") else MAX_TRACE_SOURCE_BYTES):
        raise ValueError('Compressed trace exceeds bounded analysis limit')
    trace_meta = manifest.get('trace', {})
    if not isinstance(trace_meta, dict) or trace_meta.get('closed') is not True:
        raise ValueError('Trace not certified closed; cannot infer complete frame evidence')

    ranges = [(_time(case) - margin, _time(case) + margin) for case in cases]
    details: list[dict] = [{'frames': 0, 'tracks': {}, 'proposals': [], 'deliveries': [],
                            'reject_delta': {}} for _ in cases]
    metadata = geometry = footer = False
    original_size = 0
    sha = hashlib.sha256()
    with archive.open(name) as raw:
        with (gzip.GzipFile(fileobj=raw) if name.endswith('.gz') else raw) as fp:
            for line in fp:
                original_size += len(line)
                if original_size > MAX_TRACE_SOURCE_BYTES:
                    raise ValueError('Decompressed trace exceeds safe analysis limit')
                sha.update(line)
                if b'"kind"' in line and b'"event_delivery"' in line:
                    record = json.loads(line)
                    t = float(record.get('source_time_seconds', -100))
                    for idx, (a, b) in enumerate(ranges):
                        if a <= t <= b:
                            details[idx]['deliveries'].append({
                                'time': round(t, 3), 'event_id': record.get('backend_event_id'),
                                'outcome': record.get('outcome'), 'dedup_reason': record.get('dedup_reason'),
                                'track_id': record.get('tracking_id'), 'direction': record.get('direction'),
                                'crossing_method': record.get('crossing_method')})
                    continue
                if line.startswith(b'{"kind":'):
                    record = json.loads(line)
                    kind = record.get('kind')
                    metadata |= kind == 'session_metadata'
                    geometry |= kind == 'geometry_metadata'
                    footer |= kind == 'delivery_summary' and record.get('delivery_drain_complete') is True and record.get('pending_events') == 0
                    continue
                frame_match = FRAME_PATTERN.search(line[:120])
                if not frame_match:
                    continue
                # This trace has 1-based frames but 0-based source times. Use
                # the source_time_seconds field instead of assuming a fixed fps.
                idx_time = re.search(rb'"source_time_seconds"\s*:\s*([0-9.]+)', line[:200])
                if idx_time is None:
                    continue
                t = float(idx_time.group(1))
                target = [i for i, (a, b) in enumerate(ranges) if a <= t <= b]
                if not target:
                    continue
                record = json.loads(line)
                for i in target:
                    dest = details[i]
                    dest['frames'] += 1
                    for track in record.get('gate_tracks', []):
                        track_id = track.get('track_id')
                        if not isinstance(track_id, int):
                            continue
                        point = track.get('anchor_signed')
                        if not isinstance(point, (int, float)) or not math.isfinite(point):
                            continue
                        info = dest['tracks'].setdefault(str(track_id), {
                            'label': track.get('label'), 'first_time': round(t, 3),
                            'last_time': round(t, 3), 'side_negative': False,
                            'side_positive': False, 'near_line_samples': 0, 'samples': 0})
                        info['samples'] += 1
                        info['last_time'] = round(t, 3)
                        info['side_negative'] |= point < -0.006
                        info['side_positive'] |= point > 0.006
                        info['near_line_samples'] += int(abs(point) <= 0.05)
                    for proposal in record.get('crossing_proposals', []):
                        if len(dest['proposals']) < 30:
                            dest['proposals'].append({
                                'time': proposal.get('source_time_seconds'),
                                'track_id': proposal.get('tracking_id'),
                                'direction': proposal.get('direction'),
                                'method': proposal.get('crossing_method')})
    if not (metadata and geometry and footer):
        raise ValueError('Trace missing geometry, metadata or confirmed delivery summary')
    source_hash = trace_meta.get('source_sha256')
    if source_hash and sha.hexdigest() != source_hash:
        raise ValueError('Uncompressed trace SHA-256 mismatch')
    if 'source_bytes' in trace_meta and trace_meta['source_bytes'] != original_size:
        raise ValueError('Uncompressed trace byte count mismatch')
    for entry in details:
        tracks = entry['tracks']
        entry['tracks_both_sides'] = sum(t['side_negative'] and t['side_positive'] for t in tracks.values())
        entry['near_line_tracks'] = sum(t['near_line_samples'] > 0 for t in tracks.values())
        # Bound JSON size for dense intersections. Select by observed near-line
        # and full two-sided evidence, not track id or AI class label.
        entry['tracks'] = dict(sorted(tracks.items(),
                              key=lambda item: (not (item[1]['side_negative'] and item[1]['side_positive']),
                                                -item[1]['near_line_samples'], -item[1]['samples'], item[0]))[:12])
    return {'available': True, 'source_bytes': original_size, 'source_sha256': sha.hexdigest(), 'cases': details}


def analyze(zip_path: Path, *, margin: float = 1.0) -> dict:
    if not (0.1 <= margin <= 5.0):
        raise ValueError('Review window must be within 0.1 to 5 seconds')
    report, manifest = _verified_load(zip_path)
    missed = list(report['missed_items'])
    extra = list(report['false_positive_items'])
    cases = [*missed, *extra]
    with ZipFile(zip_path) as archive:
        trace = _read_trace(archive, manifest, cases, margin)
    combined = []
    for idx, case in enumerate(cases):
        kind = 'missed' if idx < len(missed) else 'extra'
        item = {'kind': kind, 'time': round(_time(case), 3),
                'direction': case.get('direction'), 'vehicle_type': case.get('vehicle_type'),
                'ground_truth_id': case.get('ground_truth_id'), 'ai_event_id': _event_id(case),
                'diagnostic_reason': case.get('reason', 'not_classified'),
                'report_evidence': case.get('temporal_evidence'),
                'matching_audit': case.get('matching_audit'),
                'review_candidate': case.get('review_candidate')}
        if trace['available']:
            item['trace_evidence'] = trace['cases'][idx]
        combined.append(item)
    combined.sort(key=lambda row: (row['time'],row['kind'],str(row.get('ai_event_id') or '')))
    return {
        'format': 'traffic-ai-gt-case-forensics', 'version': 1,
        'session_id': report.get('session_id'), 'benchmark_id': report.get('benchmark', {}).get('id'),
        'ground_truth_total': report['ground_truth_total'], 'ai_total': report['ai_total'],
        'matched': report['matched'], 'missed': report['missed'], 'extra': report['false_positives'],
        'window_seconds': margin,
        'trace_available': trace['available'],
        'trace_reason': None if trace['available'] else trace['reason'],
        'source_trace_sha256': trace.get('source_sha256'),
        'cases': combined,
        'disclaimer': 'Read-only diagnostic. A two-sided tracker observation is not proof of a distinct physical vehicle. GT is never altered.',
    }


def format_markdown(result: dict) -> str:
    lines = [f"# GT-to-AI case audit — Session #{result['session_id']} / Benchmark #{result['benchmark_id']}",
             '', f"GT **{result['ground_truth_total']}** | AI **{result['ai_total']}** | "
             f"Matched **{result['matched']}** | Missed **{result['missed']}** | Extra **{result['extra']}**", '',
             ('Trace: complete, verified SHA-256' if result['trace_available']
              else f"Trace: UNAVAILABLE ({result['trace_reason']}); conclusions limited to backend report"),
             '', '**Audit only.** Does not relabel Ground Truth, suppress events, or claim 0 missed/extra.', '']
    for case in result['cases']:
        reason = str(case.get('diagnostic_reason') or 'unclassified').replace('`','').replace('\n',' ')
        lines.append(f"## {case['time']:.3f}s — {case['kind'].upper()} / "
                     f"{case['direction']} / {case['vehicle_type']}")
        lines.append(f"- ID: GT `{case['ground_truth_id']}`, AI `{case['ai_event_id']}`; diagnostic `{reason}`")
        t = case.get('trace_evidence')
        if t:
            lines.append(f"- Nearby trace: {t['frames']} frames; {t['tracks_both_sides']} tracks observed on both sides "
                         f"within ±{result['window_seconds']:.2f}s; {t['near_line_tracks']} near-line tracks")
            near = [v for v in t['deliveries'] if v['outcome'] == 'created']
            if near:
                lines.append('- Nearby backend created events: ' + ', '.join(
                    f"{ev['time']:.3f}s #{ev['event_id']} {ev['direction']} ({ev['crossing_method']})" for ev in near[:8]))
        lines.append('')
    lines.append('## Next step')
    lines.append('Review each case alongside the original MP4, then compare a fresh benchmark export after AI changes. ' 
                 'Never remove or add events solely to force the aggregate totals to 149.')
    return '\n'.join(lines) + '\n'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Explain every GT miss and unmatched AI event from a full benchmark export')
    parser.add_argument('--export', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, default=Path('benchmark-forensics-report'))
    parser.add_argument('--window', type=float, default=1.0)
    args = parser.parse_args(argv)
    try:
        result = analyze(args.export, margin=args.window)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / 'cases.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        (args.output_dir / 'cases.md').write_text(format_markdown(result), encoding='utf-8')
    except (ValueError, OSError, EOFError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f'[ERROR] Benchmark case audit failed closed: {exc}', file=sys.stderr)
        return 2
    print(f"Benchmark #{result['benchmark_id']} / Session #{result['session_id']}: GT {result['ground_truth_total']}, "
          f"AI {result['ai_total']}, missed {result['missed']}, extra {result['extra']}; "
          f"trace {'verified' if result['trace_available'] else 'missing'}")
    print(f'Saved {args.output_dir / "cases.json"} and cases.md')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
