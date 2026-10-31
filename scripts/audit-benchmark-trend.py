#!/usr/bin/env python3
"""V0.5.130 local-only: verified multi-run GT/AI stability and actionable review.

Read-only. A matching GT/AI timestamp is not physical-vehicle identity, and an
impressive counterfactual is not an observed counting improvement.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
MAX_RUNS = 12

def _load_module(filename, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    if spec is None or spec.loader is None:
        raise ValueError('Missing verified benchmark tool: ' + filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

repeat = _load_module('audit-benchmark-repeatability.py','trend_repeat_v05130')
compare = _load_module('compare-benchmark-exports.py','trend_compare_v05130')
quality = _load_module('audit-benchmark-quality.py','trend_quality_v05130')

GUIDANCE = {
    'clustered_gt': ('Congested gate / close timestamps',
                     'Review original MP4 frame by frame for multiple distinct vehicles. Nearby matched AI is owned by another GT; do not auto-add.'),
    'bicycle_recall': ('Bicycle detector / track / gate review',
                      'Review bicycle appearance and detection/tracking before crossing. Do not infer detector failure from absence of a DB event.'),
    'unmatched_gt': ('Unmatched ground-truth crossing',
                     'Validate GT time, direction and exact finite counting line in original MP4; inspect trace for missing proposal.'),
    'rescue_gap': ('Rescued crossing gap',
                   'Inspect the same raw-ID continuity, coherent motion and post-side confirmation; no automatic suppression.'),
    'interpolation': ('Interpolated crossing / geometry',
                      'Check finite segment, two-sided observed evidence, frame clock and full vehicle trajectory.'),
    'candidate_duplicate': ('Possible adjacent/duplicate tracks',
                            'Inspect both separate vehicles and all raw track IDs before considering deduplication.'),
    'direction': ('Direction conflict',
                  'Verify GT IN/OUT and observed side history on the original video. A time-only match is not identity.'),
    'class': ('Vehicle-class conflict',
              'Check ground-truth label and target-matched model/refiner evidence using original video.'),
    'other_extra': ('Unmatched AI event',
                    'Review full unbroken passage and corresponding trace; do not remove event from persisted DB.'),
}

def _category(case):
    k=case['kind']
    if k=='direction': return 'direction'
    if k=='class': return 'class'
    if k=='missed':
        if case.get('audit_reason')=='persisted_event_claimed_by_other_gt':return 'clustered_gt'
        if case.get('ground_truth_class')=='bicycle':return 'bicycle_recall'
        return 'unmatched_gt'
    if case.get('audit_reason')=='rescued_gap_unmatched':return 'rescue_gap'
    if case.get('audit_reason')=='interpolated_unmatched':return 'interpolation'
    if case.get('audit_reason')=='spatial_duplicate_near_gt':return 'candidate_duplicate'
    return 'other_extra'

def summarize_runs(loaded:list[dict], comparisons:list[dict], policies:list[tuple[str|None,str]]) -> dict:
    if not 3 <= len(loaded) <= MAX_RUNS or len(comparisons)!=len(loaded)-1 or len(policies)!=len(loaded):
        raise ValueError('At least three and at most twelve independently verified runs required')
    ids=[(x['report']['benchmark']['id'], x['report']['session_id']) for x in loaded]
    if len(set(ids)) != len(ids) or any(a[1]>=b[1] for a,b in zip(ids,ids[1:])):
        raise ValueError('Runs must be unique, chronological and have increasing session IDs')
    if not all(x.get('scoring_comparable') is True and x.get('same_ground_truth') is True and
               x.get('same_source_geometry') is True for x in comparisons):
        raise ValueError('Comparison requires identical source, geometry, complete scored GT and matching tolerance')
    reports=[x['report'] for x in loaded]
    signs=[repeat._signatures(r) for r in reports]
    latest=reports[-1]
    # Counter intersection counts repeated occurrences across *all* runs,
    # instead of just membership in a set (duplicate marks are not erased).
    common=signs[0].copy()
    for s in signs[1:]: common &= s
    persistent_remaining=common.copy()
    near_previous=signs[-2].copy()
    rows=[]
    for kind, list_name, _ in repeat.PARTS:
        for entry in latest[list_name]:
            signature=repeat._signature(kind,entry)
            persistent=persistent_remaining[signature]>0
            if persistent: persistent_remaining[signature]-=1
            repeated=near_previous[signature]>0
            if repeated: near_previous[signature]-=1
            case=quality._issue(kind,entry)
            category=_category(case)
            case['focus']=category
            case['focus_description'],case['review_action']=GUIDANCE[category]
            case['persistent_all_runs']=persistent
            case['repeated_previous_run']=repeated
            case['runs_with_signature']=sum(s[signature]>0 for s in signs)
            case['first_benchmark_seen']=next(x['report']['benchmark']['id'] for x,s in zip(loaded,signs) if s[signature]>0)
            case['requires_original_video']=True
            case['identity_proven']=False
            rows.append(case)
    rows.sort(key=lambda x:(x['time'],x['kind'],x.get('ai_event_id') or 0))
    for n,case in enumerate(rows,1):case['review_id']=f'REVIEW-{n:02d}'
    same_crossings=all(c['same_recorded_ai_crossing_signatures'] is True for c in comparisons)
    stable_metrics=all(all(c['deltas'].get(m)==0 for m in ('matched','missed','false_positives',
                           'class_mismatches','direction_mismatches')) for c in comparisons)
    digests=[digest for digest, status in policies if status=='complete']
    same_policy=(len(digests)==len(policies) and len(set(digests))==1) if len(digests)==len(policies) else None
    return {'format':'traffic-ai-benchmark-multi-run-trend','schema_version':1,
            'runs':[{'benchmark_id':b,'session_id':s,'gt':r['ground_truth_total'],
                     'ai':r['ai_total'],'matched':r['matched'],'missed':r['missed'],
                     'extra':r['false_positives'],'direction':r['direction_mismatches'],
                     'class':r['class_mismatches']} for (b,s),r in zip(ids,reports)],
            'integrity':{'verified_sha256':True,'scored_gt_compatible':True,'source_geometry_compatible':True,
                         'same_ai_crossing_signatures_all_runs':same_crossings,
                         'same_effective_policy_all_runs':same_policy,
                         'policy_status':[x[1] for x in policies]},
            'summary':{'latest_issue_count':len(rows),
                       'persistent_issue_signatures':sum(c['persistent_all_runs'] for c in rows),
                       'new_since_previous':sum(not c['repeated_previous_run'] for c in rows),
                       'change_observed':not (same_crossings and stable_metrics),
                       'improvement_observed':(float(reports[-1].get('counting_f1') or 0) > float(reports[0].get('counting_f1') or 0) and
                          reports[-1]['missed'] <= reports[0]['missed'] and
                          reports[-1]['false_positives'] <= reports[0]['false_positives']),
                       'same_measured_metrics_all_runs':stable_metrics},
            'read_only':True,'algorithm_modified':False,'accuracy_improvement_claimed':False,
            'warnings':['Three matching runs do not prove the same physical vehicle identity.',
                        'No auto-suppression, auto-counting, GT changes, DB edits or model fine-tuning is performed.',
                        'Review actual video and contiguous trace before changing the counting or classification policy.',
                        'The comparison is of recorded events, not an independent GPU replay.'],
            'issues':rows}

def analyze(exports:list[Path]) -> dict:
    if not 3 <= len(exports) <= MAX_RUNS:
        raise ValueError('Provide between 3 and 12 benchmark ZIPs in chronological order')
    if len({x.resolve() for x in exports})!=len(exports):
        raise ValueError('Duplicate benchmark ZIP paths')
    loaded=[compare._read_evidence(path) for path in exports]  # validates all ZIP member SHA-256
    comparisons=[compare.compare(loaded[i-1],loaded[i]) for i in range(1,len(loaded))]
    policies=[repeat._policy_digest(path,entry['manifest']) for path,entry in zip(exports,loaded)]
    return summarize_runs(loaded, comparisons,policies)

def write_outputs(result:dict,out:Path):
    out.mkdir(parents=True,exist_ok=True)
    (out/'benchmark-trend.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    cols=('review_id','timecode','kind','focus','persistent_all_runs','runs_with_signature',
          'repeated_previous_run','first_benchmark_seen','ground_truth_id','ai_event_id','tracking_id',
          'ground_truth_direction','ai_direction','ground_truth_class','ai_class','crossing_method',
          'audit_reason','focus_description','review_action')
    with (out/'benchmark-trend.csv').open('w',newline='',encoding='utf-8-sig') as fh:
        writer=csv.DictWriter(fh,fieldnames=cols,extrasaction='ignore');writer.writeheader();writer.writerows(result['issues'])
    s=result['summary'];a=result['integrity'];b=result['runs']
    lines=['# Traffic AI — đối chiếu nhiều phiên benchmark (chỉ đọc)','',
        f'- Các benchmark: **{", ".join("#"+str(x["benchmark_id"]) for x in b)}**',
        f'- Tất cả SHA-256 và GT/source/geometry tương thích: **{a["verified_sha256"] and a["scored_gt_compatible"]}**.',
        f'- Chữ ký AI giống nhau giữa mọi lần: **{a["same_ai_crossing_signatures_all_runs"]}** (không chứng minh đúng GT).',
        f'- Chính sách AI hiệu lực giống nhau: **{a["same_effective_policy_all_runs"]}**.',
        f'- Hồ sơ lỗi lần cuối: **{s["latest_issue_count"]}**, lặp qua tất cả phiên: **{s["persistent_issue_signatures"]}**, mới: **{s["new_since_previous"]}**.',
        f'- Các chỉ số chấm giữ nguyên: **{s["same_measured_metrics_all_runs"]}**.',
        '', '| Timecode | Lỗi | Lặp tất cả | Trọng tâm cần xem |', '|---|---|---|---|']
    for case in result['issues']:
        lines.append('| {} | {} | {} | {} |'.format(case['timecode'],case['kind'],
                     'Có' if case['persistent_all_runs'] else 'Không',case['focus_description']))
    lines.extend(['','## Giới hạn và an toàn',*(f'- {w}' for w in result['warnings']),''])
    (out/'benchmark-trend.md').write_text('\n'.join(lines),encoding='utf-8')

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--exports',required=True,type=Path,nargs='+')
    p.add_argument('--output-dir',type=Path,default=Path('benchmark-trend-audit'))
    args=p.parse_args(argv)
    try:
        result=analyze(args.exports)
        write_outputs(result,args.output_dir)
    except (ValueError,KeyError,TypeError,OSError,RuntimeError,EOFError,json.JSONDecodeError) as e:
        print('[FAIL] Verified benchmark trend: '+str(e),file=sys.stderr)
        return 2
    s=result['summary']
    print('[OK] Multi-run benchmark: {} verified sessions; {} latest issues; {} persistent, {} new.'.format(
          len(result['runs']),s['latest_issue_count'],s['persistent_issue_signatures'],s['new_since_previous']))
    print('[OK] Read-only JSON/CSV/Markdown: '+str(args.output_dir))
    return 0
if __name__=='__main__':raise SystemExit(main())
