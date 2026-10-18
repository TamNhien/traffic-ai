#!/usr/bin/env python3
"""V0.5.102: verified, read-only GT/AI temporal-neighbor diagnostics.

Find event candidates just OUTSIDE the configured scoring window, and expose
nearby events already allocated to another Ground Truth mark. No inference,
identity guesses, rematching, ground-truth edits, or persistence changes.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import sys
from pathlib import Path
from zipfile import ZipFile


def _forensics():
    path = Path(__file__).with_name('benchmark-forensics.py')
    spec = importlib.util.spec_from_file_location('traffic_ai_verified_temporal_102', path)
    if spec is None or spec.loader is None:
        raise ValueError('Verified forensics module unavailable')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def candidates(missed: list[dict], extra: list[dict], matched: list[dict],
               events: list[dict], gt: list[dict], *, tolerance: float,
               horizon: float = 2.0) -> list[dict]:
    if (not math.isfinite(tolerance) or tolerance <= 0 or
        not math.isfinite(horizon) or horizon <= tolerance or horizon > 5):
        raise ValueError('Search horizon must exceed tolerance and be at most 5 seconds')
    owners = {x['ai_event_id']: x['ground_truth_id'] for x in matched}
    extra_ids = {x['ai_event_id'] for x in extra}
    missed_ids = {x['ground_truth_id'] for x in missed}
    if len(owners) != len(matched):
        raise ValueError('Duplicate AI assignment in matched items')
    if len(missed_ids) != len(missed) or len(extra_ids) != len(extra):
        raise ValueError('Duplicate unmatched event/GT ID')
    result = []
    for kind, records, other in (('missed', missed, events), ('extra', extra, gt)):
        for record in records:
            t = float(record['time'])
            if not math.isfinite(t) or t < 0:
                raise ValueError('Invalid case time')
            choices = []
            for neighbor in other:
                nt = neighbor.get('source_time_seconds')
                if isinstance(nt, bool) or not isinstance(nt, (int, float)) or not math.isfinite(nt):
                    continue
                dt = float(nt) - t
                if abs(dt) > horizon:
                    continue
                owner = owners.get(neighbor['id']) if kind == 'missed' else None
                match_owner = next((m['ai_event_id'] for m in matched
                                   if m['ground_truth_id'] == neighbor['id']), None) if kind == 'extra' else None
                choices.append({
                    'neighbor_id': neighbor['id'], 'delta_s': round(dt, 4),
                    'direction': neighbor['direction'], 'vehicle_type': neighbor['vehicle_type'],
                    'within_scoring_window': abs(dt) <= tolerance,
                    'same_direction': neighbor['direction'] == record['direction'],
                    'same_vehicle_type': neighbor['vehicle_type'] == record['vehicle_type'],
                    'already_matched_to': owner if kind == 'missed' else match_owner,
                    'unmatched_neighbor': (neighbor['id'] in extra_ids if kind == 'missed' else neighbor['id'] in missed_ids),
                })
            choices.sort(key=lambda x: (abs(x['delta_s']),x['neighbor_id']))
            close = choices[:5]
            if kind == 'missed':
                if any(c['within_scoring_window'] and c['already_matched_to'] is not None for c in choices):
                    reason = 'temporal_competition_not_identity_proof'
                elif any(not c['within_scoring_window'] and c['same_direction'] for c in choices):
                    reason = 'outside_tolerance_same_direction_candidate'
                else:
                    reason = 'no_matching_window_crossing'
            else:
                reason = 'unmatched_ai_requires_video_review'
            result.append({
                'kind': kind, 'case_id': record.get('ground_truth_id') if kind=='missed' else record.get('ai_event_id'),
                'time_s': round(t,4), 'direction': record['direction'],
                'vehicle_type': record['vehicle_type'], 'review_category': reason,
                'neighbors': close, 'total_neighbors_in_horizon': len(choices),
                'physical_identity_proven': False,
            })
    return sorted(result,key=lambda x: (x['time_s'],x['kind']))


def analyze(export: Path, *, horizon: float = 2.0) -> dict:
    verify = _forensics()
    # Reads the verified compressed trace through EOF, validates its original
    # SHA256 and required delivery footer (not only ZIP CRC/manifest digests).
    baseline = verify.analyze(export, margin=max(1.0,horizon))
    if not baseline['trace_available']:
        raise ValueError('Complete verified trace required')
    with ZipFile(export) as z:
        report=json.loads(z.read('report.json'))
        events=json.loads(z.read('events.json'))
        gt=json.loads(z.read('ground-truth.json'))
    tolerance=float(report['benchmark']['tolerance_seconds'])
    result=candidates(report['missed_items'], report['false_positive_items'],
                      report['matched_items'],events,gt,tolerance=tolerance,horizon=horizon)
    if len(result)!=report['missed']+report['false_positives']:
        raise ValueError('Case count mismatch')
    return {
        'format':'traffic-ai-verified-temporal-neighbors','version':1,
        'session_id':baseline['session_id'],'benchmark_id':baseline['benchmark_id'],
        'ground_truth_total':baseline['ground_truth_total'], 'ai_total':baseline['ai_total'],
        'matched':baseline['matched'], 'missed':baseline['missed'], 'extra':baseline['extra'],
        'tolerance_seconds':tolerance,'search_horizon_seconds':horizon,
        'verified_trace_sha256':baseline['source_trace_sha256'],
        'cases':result,
        'disclaimer': 'Review-only clock evidence: temporal/direction proximity does not prove identity. No GT, AI event, matcher or database changes.',
    }


def markdown(report: dict) -> str:
    lines=[f'# Timecode witness - Benchmark #{report["benchmark_id"]}, Session #{report["session_id"]}',
           '',f'GT {report["ground_truth_total"]} / AI {report["ai_total"]} / matched {report["matched"]} / missed {report["missed"]} / extra {report["extra"]}',
           f'Scoring window: +/-{report["tolerance_seconds"]:.2f}s. Review horizon: +/-{report["search_horizon_seconds"]:.2f}s.',
           '', '**Review-only, no changes to counted events or Ground Truth.**', '',
           '| Time | Type | Case ID | Direction | Category | Nearest event / GT |', '|---:|---|---:|---|---|---|']
    for case in report['cases']:
        c=case['neighbors'][0] if case['neighbors'] else None
        n=(f'#{c["neighbor_id"]} ({c["delta_s"]:+.3f}s, {c["direction"]}, '
           f'{"already assigned" if c["already_matched_to"] is not None else "unassigned"})' if c else 'no neighbor within horizon')
        lines.append(f'| {case["time_s"]:.3f} | {case["kind"]} | {case["case_id"]} | {case["direction"]} | {case["review_category"]} | {n} |')
    lines+=['','Nearby records are NOT evidence of the same physical vehicle. Use the original video and verified track/geometry witnesses before changing runtime thresholds.','']
    return '\n'.join(lines)


def write(report: dict, output: Path) -> None:
    output.mkdir(parents=True,exist_ok=True)
    (output/'temporal-neighbors.json').write_text(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
    (output/'temporal-neighbors.md').write_text(markdown(report),encoding='utf-8')
    with (output/'temporal-neighbors.csv').open('w',encoding='utf-8-sig',newline='') as f:
        wr=csv.DictWriter(f,fieldnames=['time_s','kind','case_id','direction','vehicle_type','review_category','nearest_neighbor_id','nearest_delta_s','nearest_direction','nearest_assigned_to'])
        wr.writeheader()
        for row in report['cases']:
            neighbor=row['neighbors'][0] if row['neighbors'] else {}
            wr.writerow(dict(time_s=row['time_s'],kind=row['kind'],case_id=row['case_id'],direction=row['direction'],vehicle_type=row['vehicle_type'],review_category=row['review_category'],nearest_neighbor_id=neighbor.get('neighbor_id'),nearest_delta_s=neighbor.get('delta_s'),nearest_direction=neighbor.get('direction'),nearest_assigned_to=neighbor.get('already_matched_to')))


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,default=Path('temporal-neighbor-audit'))
    parser.add_argument('--horizon',type=float,default=2.0)
    args=parser.parse_args(argv)
    try:
        report=analyze(args.export,horizon=args.horizon)
        write(report,args.output_dir)
    except (ValueError, KeyError, OSError, TypeError, json.JSONDecodeError) as exc:
        print(f'[ERROR] No review report written: {exc}',file=sys.stderr)
        return 2
    print(f'Benchmark #{report["benchmark_id"]}: missed {report["missed"]}, extra {report["extra"]}; verified trace, {len(report["cases"])} review cases.')
    print(f'Reports: {args.output_dir}')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
