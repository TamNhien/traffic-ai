#!/usr/bin/env python3
"""Read-only cross-run GT witness for Traffic AI V0.5.83.

This does NOT assert actual GT accuracy for the newer run (which has no GT file).
It identifies which *historically matched* baseline AI events disappeared in a
new trace, including whether those baseline matches had correct IN/OUT and class.
Event identity is approximate by time/direction/position; never auto-edit GT.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
from zipfile import ZipFile, BadZipFile


def load_replay_module():
    path = Path(__file__).with_name('replay-diff.py')
    spec = importlib.util.spec_from_file_location('traffic_replay_diff', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def baseline_documents(path: Path) -> tuple[dict, list[dict]]:
    # Both report and events belong to the *same exported benchmark*. Never
    # accept unverified sidecar data from another run or require credentials.
    with ZipFile(path) as archive:
        names = set(archive.namelist())
        if not {'report.json', 'events.json', 'manifest.json'} <= names:
            raise ValueError('Reference must be a full benchmark ZIP with report and events')
        manifest = json.loads(archive.read('manifest.json'))
        if manifest.get('format') != 'traffic-ai-benchmark-diagnostics':
            raise ValueError('Unknown benchmark manifest')
        for filename in ('report.json', 'events.json'):
            info = archive.getinfo(filename)
            if info.file_size > 16 * 1024 * 1024:
                raise ValueError(f'{filename} is too large')
            payload = archive.read(filename)
            record = (manifest.get('files') or {}).get(filename)
            if not record or record.get('bytes') != len(payload) or record.get('sha256') != sha256(payload).hexdigest():
                raise ValueError(f'{filename} checksum/size mismatch')
        report = json.loads(archive.read('report.json'))
        events = json.loads(archive.read('events.json'))
    if not isinstance(report, dict) or not isinstance(events, list) or len(events) > 100_000:
        raise ValueError('Invalid baseline records')
    if not (report.get('report_readiness') or {}).get('scoring_available'):
        raise ValueError('Baseline benchmark must have verified Ground Truth scoring')
    return report, events


def classify_removed_events(removed: list[dict], report: dict, events: list[dict]) -> list[dict]:
    matched_by_event = {int(m['ai_event_id']): m for m in report.get('matched_items', [])}
    output = []
    for crossing in removed:
        time = float(crossing['seconds'])
        x, y = [float(v) for v in crossing['position']]
        candidates = [e for e in events if e.get('source_time_seconds') is not None
                      and str(e.get('direction')) == crossing['direction']
                      and abs(float(e['source_time_seconds']) - time) <= 0.08
                      and abs(float(e.get('crossing_x', -1)) - x) <= 0.015
                      and abs(float(e.get('crossing_y', -1)) - y) <= 0.015]
        item = {'lost_ai': crossing, 'baseline_link': 'unverified',
                'baseline_ground_truth': None, 'direction_correct': None,
                'class_correct': None}
        if len(candidates) == 1:
            match = matched_by_event.get(int(candidates[0]['id']))
            if match:
                item['baseline_link'] = 'historically_timecode_matched'
                item['baseline_ground_truth'] = {
                    'id': match['ground_truth_id'],
                    'seconds': match['ground_truth_time'],
                    'direction': match['ground_truth_direction'],
                    'vehicle_type': match['ground_truth_vehicle_type']}
                item['direction_correct'] = bool(match['direction_correct'])
                item['class_correct'] = bool(match['class_correct'])
            else:
                item['baseline_link'] = 'historically_unmatched_ai'
        elif len(candidates) > 1:
            item['baseline_link'] = 'ambiguous_baseline_event'
        output.append(item)
    return output


def build_report(reference, current, baseline_report, events, module) -> dict:
    replay = module.summarize(reference, current)
    removed = classify_removed_events(replay['created_removed'], baseline_report, events)
    return {
        'format': 'traffic-ai-gt-replay-witness',
        'version': 1,
        'warning': ('GT labels are available ONLY for the reference run. A lost baseline match '
                    'is not proof of a newly missed physical vehicle; timecode pairing may have '
                    'been wrong-direction or wrong-class. The current run must be benchmarked separately.'),
        'reference_session': reference.session_id,
        'current_session': current.session_id,
        'reference_gt': baseline_report['ground_truth_total'],
        'reference_matched_timecode': baseline_report['matched'],
        'reference_wrong_direction': sum(not item['direction_correct'] for item in baseline_report['matched_items']),
        'replay_summary': replay['summary'],
        'lost_event_witnesses': removed,
        'new_events': replay['created_introduced'],
        'decision_changes': replay['decision_changes'],
    }


def markdown(data: dict) -> str:
    lines = [
        '# GT-linked cross-run evidence (V0.5.83)', '',
        f"Reference Session #{data['reference_session']} -> current #{data['current_session']}", '',
        '> ' + data['warning'], '',
        f"- Reference GT: **{data['reference_gt']}**; timecode matches: **{data['reference_matched_timecode']}**",
        f"- Wrong-direction pairs in reference: **{data['reference_wrong_direction']}**",
        f"- Lost created events: **{data['replay_summary']['created_removed']}**",
        f"- New created events: **{data['replay_summary']['created_introduced']}**", '',
        '## Lost event and historical GT evidence', '',
    ]
    for item in data['lost_event_witnesses']:
        crossing = item['lost_ai']
        lines.append(f"- **{crossing['seconds']:.3f}s**, {crossing['direction'].upper()} {crossing['vehicle_type']} "
                     f"(frame {crossing['frame']}, {crossing['method']}): {item['baseline_link']}.")
        if item['baseline_ground_truth']:
            gt = item['baseline_ground_truth']
            lines.append(f"  - Historical GT: **{gt['seconds']:.3f}s {gt['direction'].upper()} {gt['vehicle_type']}**; "
                         f"direction correct **{item['direction_correct']}**, class correct **{item['class_correct']}**.")
    if not data['lost_event_witnesses']:
        lines.append('No lost created event was detected.')
    lines += ['', '## Scope', '',
              'This is an event regression witness, not a replacement benchmark. It does not change '
              'the model, counting rules, Ground Truth, or database.', '']
    return '\n'.join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Find lost created events and historical GT direction evidence')
    parser.add_argument('--reference-benchmark', type=Path, required=True)
    parser.add_argument('--current-trace', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, default=Path('gt-replay-witness-report'))
    parser.add_argument('--strict', action='store_true', help='Fail on lost/new created events or decision flips')
    args = parser.parse_args(argv)
    try:
        if args.reference_benchmark.resolve() == args.current_trace.resolve():
            raise ValueError('Use distinct reference/current files')
        module = load_replay_module()
        prev = module.load_trace(args.reference_benchmark)
        curr = module.load_trace(args.current_trace)
        report, events = baseline_documents(args.reference_benchmark)
        if int(report['session_id']) != prev.session_id:
            raise ValueError('Reference report session differs from signed trace')
        result = build_report(prev, curr, report, events, module)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / 'gt-replay-witness.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        (args.output_dir / 'gt-replay-witness.md').write_text(markdown(result), encoding='utf-8')
        s = result['replay_summary']
        print(f"Session #{prev.session_id} -> #{curr.session_id}: lost {s['created_removed']}, "
              f"new {s['created_introduced']}, changed {s['decision_changes']}")
        print(f"Report: {args.output_dir / 'gt-replay-witness.md'}")
        if args.strict and (s['created_removed'] or s['created_introduced'] or s['decision_changes']):
            print('[FAIL] GT-linked replay stability; not a GT accuracy result', file=sys.stderr)
            return 1
        print('[PASS] Evidence validated; not a GT accuracy certification')
        return 0
    except (OSError, ValueError, KeyError, TypeError, BadZipFile) as exc:
        print(f'[ERROR] GT-replay evidence invalid: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
