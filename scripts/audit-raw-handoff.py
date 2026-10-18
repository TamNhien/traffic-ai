#!/usr/bin/env python3
"""V0.5.100 verified read-only replay of *recorded* raw-ID owner handoffs.

This is not a detector/model replay and MUST NOT mutate GT or persisted events.
It verifies the benchmark archive first, then its entire original gzip stream.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from zipfile import ZipFile

AI_SERVICE = Path(__file__).resolve().parents[1] / 'ai-service'
sys.path.insert(0, str(AI_SERVICE))
from app.raw_handoff_guard import RawHandoffCrossingGuard  # noqa: E402

MAX_TRACE_SOURCE_BYTES = 512 * 1024 * 1024


def analyze(archive: Path) -> dict:
    verifier_path = Path(__file__).with_name('benchmark-gate.py')
    spec = importlib.util.spec_from_file_location('raw_handoff_benchmark_gate', verifier_path)
    if spec is None or spec.loader is None:
        raise ValueError('Missing benchmark archive verifier')
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    report, manifest = verifier.load_evidence(archive)
    meta = manifest.get('trace') or {}
    if meta.get('closed') is not True or meta.get('available') is not True:
        raise ValueError('Closed, certified benchmark trace is required')
    if meta.get('source_bytes', 0) > MAX_TRACE_SOURCE_BYTES:
        raise ValueError('Trace exceeds safety limit')

    guard = RawHandoffCrossingGuard()
    cases = []
    number_of_frames = 0
    number_of_proposals = 0
    actual_bytes = 0
    sha = hashlib.sha256()
    saw_session_metadata = saw_geometry_metadata = saw_closed_footer = False
    with ZipFile(archive) as z:
        with z.open('benchmark-trace.jsonl.gz') as raw, gzip.GzipFile(fileobj=raw) as fp:
            for line in fp:
                actual_bytes += len(line)
                if actual_bytes > MAX_TRACE_SOURCE_BYTES:
                    raise ValueError('Decompressed trace exceeds safety limit')
                sha.update(line)
                if b'"kind"' in line[:120]:
                    record = json.loads(line)
                    kind = record.get('kind')
                    saw_session_metadata |= kind == 'session_metadata'
                    saw_geometry_metadata |= kind == 'geometry_metadata'
                    saw_closed_footer |= (kind == 'delivery_summary'
                                          and record.get('delivery_drain_complete') is True
                                          and record.get('pending_events') == 0)
                if b'"frame_index"' not in line[:120]:
                    continue
                row = json.loads(line)
                if 'gate_tracks' not in row:
                    continue
                frame = row['frame_index']
                if not isinstance(frame, int) or isinstance(frame, bool) or frame != number_of_frames+1:
                    raise ValueError('Non-contiguous benchmark frame trace')
                number_of_frames += 1
                raw_for_canonical = {}
                for track in row['gate_tracks']:
                    if track.get('label') in ('motorcycle', 'bicycle'):
                        raw_id = track.get('raw_track_id')
                        canonical = track.get('track_id')
                        rect = track.get('rect')
                        if not isinstance(raw_id, int) or not isinstance(canonical, int) or not isinstance(rect, list):
                            continue
                        guard.observe(raw_id, canonical, frame, tuple(rect))
                        raw_for_canonical[canonical] = raw_id
                for proposal in row.get('crossing_proposals', []):
                    if proposal.get('stage') not in ('committed_before_submit', 'submitted_after_guard'):
                        continue
                    number_of_proposals += 1
                    canonical = proposal.get('tracking_id')
                    raw_id = raw_for_canonical.get(canonical)
                    if raw_id is None:
                        continue
                    proof = guard.duplicate_of(
                        raw_id, canonical, frame, proposal['direction'],
                        proposal.get('crossing_x'), proposal.get('crossing_y'),
                        crossing_method=proposal.get('crossing_method'),
                    )
                    if proof:
                        cases.append({
                            'source_time_seconds': proposal.get('source_time_seconds'),
                            'observed_frame_index': frame, 'crossing_method': proposal.get('crossing_method'),
                            **proof,
                        })
                    else:
                        guard.note_passage(canonical, frame, proposal['direction'],
                                           proposal.get('crossing_x'), proposal.get('crossing_y'))
    if actual_bytes != meta.get('source_bytes') or sha.hexdigest() != meta.get('source_sha256'):
        raise ValueError('Source trace digest does not match certified manifest')
    if not (saw_session_metadata and saw_geometry_metadata and saw_closed_footer):
        raise ValueError('Source trace lacks verified metadata/geometry/delivery closure')
    return {
        'format': 'traffic-ai-raw-handoff-shadow-replay',
        'version': '0.5.100',
        'benchmark_id': report['benchmark']['id'],
        'session_id': report['session_id'],
        'ground_truth_total': report['ground_truth_total'],
        'ai_total': report['ai_total'],
        'matched': report['matched'],
        'missed': len(report['missed_items']),
        'extra': len(report['false_positive_items']),
        'frames': number_of_frames,
        'original_proposals': number_of_proposals,
        'strict_raw_handoff_candidates': len(cases),
        'source_trace_sha256': sha.hexdigest(),
        'limitations': [
            'Historical raw-ID observations are replayed, not live YOLO inference.',
            'Results are candidates on recorded tracks; future model/tracker behavior may change.',
            'No correction to GT or persisted events; no new F1 score is claimed.',
            'Passing a handoff guard cannot prove physical identity in overlapping real convoys.',
        ],
        'cases': cases,
    }


def save(result: dict, folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder/'raw-handoff-audit.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    md = [f'# Raw-ID handoff shadow audit — Benchmark #{result["benchmark_id"]} / Session #{result["session_id"]}', '',
          f'- GT: {result["ground_truth_total"]}; AI: {result["ai_total"]}; matched: {result["matched"]}; missed: {result["missed"]}; extra: {result["extra"]}.',
          f'- Verified frames: {result["frames"]}; recorded proposals: {result["original_proposals"]}.',
          f'- Strict raw handoff candidates: **{result["strict_raw_handoff_candidates"]}**.',
          f'- Certified source SHA-256: `{result["source_trace_sha256"]}`.',
          '', '## Candidates', '']
    for c in result['cases']:
        md.append(f'- Frame {c["observed_frame_index"]}, source {c["source_time_seconds"]}s: '
                  f'canonical {c["former_canonical_id"]} → {c["current_canonical_id"]}, '
                  f'raw {c["shared_raw_track_id"]}, Δframes {c["frame_delta"]}, '
                  f'IoU {c["handoff_box_iou"]}, Δxy ({c["crossing_dx"]}, {c["crossing_dy"]}), '
                  f'{c["direction"]}.')
    md.extend(['', '## Limitations', ''] + ['- '+line for line in result['limitations']])
    (folder/'raw-handoff-audit.md').write_text('\n'.join(md)+'\n',encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, default=Path('raw-handoff-audit'))
    args = parser.parse_args()
    try:
        result = analyze(args.export)
        save(result,args.output_dir)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print('[FAIL] Raw handoff audit:',exc,file=sys.stderr)
        return 2
    print(f'[OK] Certified Benchmark #{result["benchmark_id"]}, '
          f'{result["frames"]} frames, {result["strict_raw_handoff_candidates"]} causal candidates')
    print('Report:',args.output_dir/'raw-handoff-audit.md')
    return 0


if __name__ == '__main__':
    sys.exit(main())
