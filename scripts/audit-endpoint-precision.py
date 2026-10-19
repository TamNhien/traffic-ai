#!/usr/bin/env python3
"""Verified, read-only A/B projection of V0.5.106 endpoint precision policy.

This is NOT model inference. It does not mutate GT, events or database and
cannot establish physical vehicle identity or final precision gains.
"""
from __future__ import annotations
import argparse, gzip, importlib.util, json, sys
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'ai-service'))
from app.finite_endpoint_guard import endpoint_precision_rejection


def analyze(export: Path) -> dict:
    util = ROOT/'scripts'/'audit-gate-coverage.py'
    spec = importlib.util.spec_from_file_location('endpoint_verified_audit', util)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._verify(export)  # Complete trace/digest and event/GT integrity first.
    with ZipFile(export) as z:
        report = json.loads(z.read('report.json'))
        events = json.loads(z.read('events.json'))
        gt = json.loads(z.read('ground-truth.json'))
        target = {int(e['tracking_id']):[] for e in events if e.get('crossing_method') == 'interpolated' and e.get('vehicle_type') in ('motorcycle','bicycle')}
        evidence = {}
        line = None
        with gzip.open(z.open('benchmark-trace.jsonl.gz'),'rt',encoding='utf-8') as frames:
            for row in frames:
                obs = json.loads(row)
                if obs.get('kind') == 'geometry_metadata':
                    line = obs.get('line')
                    continue
                if 'frame_index' not in obs:
                    continue
                if line is None:
                    raise ValueError('Missing verified geometry')
                for tr in obs.get('gate_tracks',[]):
                    tid = tr.get('track_id')
                    if tid in target and tr.get('final_gate_decision') in ('primary-accepted','secondary-accepted'):
                        target[tid].append({
                            'frame':obs['frame_index'], 'time':obs['source_time_seconds'],
                            'center_signed':tr.get('center_signed'),
                            'decision':tr.get('final_gate_decision'),
                        })
    matched = {e['ai_event_id'] for e in report['matched_items']}
    extra = {e['ai_event_id'] for e in report['false_positive_items']}
    rows=[]
    for event in events:
        if event.get('crossing_method') != 'interpolated' or event.get('vehicle_type') not in ('motorcycle','bicycle'):
            continue
        candidates = sorted((v for v in target.get(int(event['tracking_id']),[]) if abs(v['time']-event['source_time_seconds'])<=.75),key=lambda v:abs(v['time']-event['source_time_seconds']))
        if not candidates:continue
        chosen=candidates[0]
        rejection = endpoint_precision_rejection(
            (tuple(line[0]),tuple(line[1])),
            (event['crossing_x'],event['crossing_y']),
            chosen['center_signed'], event['direction'],event['vehicle_type'],event['crossing_method'],
        )
        if rejection:
            rows.append({
                'ai_event_id':event['id'],'source_time_seconds':event['source_time_seconds'],
                'tracking_id':event['tracking_id'],'direction':event['direction'],
                'score_assignment':'matched' if event['id'] in matched else 'unmatched' if event['id'] in extra else 'unknown',
                'gate_evidence_frame':chosen['frame'], 'policy':rejection,
            })
    return {
        'format':'traffic-ai-finite-endpoint-counterfactual','version':1,
        'benchmark_id':report['benchmark']['id'],'session_id':report['session_id'],
        'observed_ai_total':len(events),'observed_gt_total':len(gt),
        'observed_matched':report['matched'],'observed_missed':report['missed'],
        'observed_extra':report['false_positives'],
        'flagged_event_count':len(rows),'flagged_previously_matched':sum(x['score_assignment']=='matched' for x in rows),
        'flagged_previously_unmatched':sum(x['score_assignment']=='unmatched' for x in rows),
        'candidates':rows,
        'disclaimer':'Read-only, past-trace approximation. Not a new inference run; no identity proof and no score or GT mutation. Re-run identical clip after upgrade to verify.'
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--export',required=True,type=Path)
    parser.add_argument('--output-directory',required=True,type=Path)
    a=parser.parse_args()
    report=analyze(a.export)
    a.output_directory.mkdir(parents=True,exist_ok=True)
    (a.output_directory/'endpoint-precision.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    lines=[f"# Finite endpoint counterfactual | Benchmark #{report['benchmark_id']} / Session #{report['session_id']}", '',
           f"Observed {report['observed_gt_total']} GT / {report['observed_ai_total']} AI / {report['observed_missed']} missed / {report['observed_extra']} extra.",
           f"Flagged {report['flagged_event_count']} candidates: {report['flagged_previously_matched']} previously matched, {report['flagged_previously_unmatched']} previously unmatched.",'',
           '| Time(s) | Event | Track | Assignment | Projection | Center signed |','|---:|---:|---:|---|---:|---:|']
    for r in report['candidates']:
        lines.append(f"| {r['source_time_seconds']:.3f} | {r['ai_event_id']} | {r['tracking_id']} | {r['score_assignment']} | {r['policy']['projection']:.4f} | {r['policy']['center_signed']:.4f} |")
    lines += ['', '**Warning:** '+report['disclaimer']]
    (a.output_directory/'endpoint-precision.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(f"Benchmark #{report['benchmark_id']} / Session #{report['session_id']}: {report['flagged_event_count']} endpoint candidates; reports: {a.output_directory}")

if __name__=='__main__':main()
