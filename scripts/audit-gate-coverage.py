#!/usr/bin/env python3
"""V0.5.103: verified, read-only near-gate spatial witnesses for benchmark misses/extras.

Never infers physical vehicle identity or changes Ground Truth, source events or scoring.
A crossing-like *span* is a review candidate, not permission to insert a count.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import importlib.util
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from zipfile import ZipFile


def _verify(export: Path):
    path = Path(__file__).with_name('benchmark-forensics.py')
    spec = importlib.util.spec_from_file_location('traffic_ai_gate_coverage_verify', path)
    if spec is None or spec.loader is None:
        raise ValueError('Benchmark verification module missing')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    result = mod.analyze(export, margin=1.25)
    if not result.get('trace_available'):
        raise ValueError('Complete verified trace required')
    return result


def _finite_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def point_gate_geometry(point, line, width, height):
    """Normalized finite segment projection and perpendicular distance."""
    if not isinstance(point, (list, tuple)) or len(point) != 2 or not all(_finite_number(x) for x in point):
        return None
    if width <= 0 or height <= 0:
        raise ValueError('Invalid trace dimensions')
    x, y = float(point[0]) / width, float(point[1]) / height
    (ax, ay), (bx, by) = line
    dx, dy = bx - ax, by - ay
    n2 = dx * dx + dy * dy
    if n2 < 1e-10:
        raise ValueError('Degenerate gate')
    u = ((x - ax) * dx + (y - ay) * dy) / n2
    signed = (dx * (y - ay) - dy * (x - ax)) / math.sqrt(n2)
    return u, signed


def case_witnesses(case: dict, observations: list[dict], *, near_radius: float = .035,
                   max_gap_frames: int = 6) -> dict:
    """Summarize observed *geometry only*, without guessing object identity."""
    if not _finite_number(near_radius) or not 0 < near_radius <= .1:
        raise ValueError('Invalid near-gate radius')
    tracks = defaultdict(list)
    observed = 0
    for item in observations:
        observed += 1
        tid = item['track_id']
        tracks[tid].append(item)
    candidates = []
    for tid, values in tracks.items():
        values.sort(key=lambda z: z['frame'])
        near = [v for v in values if -0.05 <= v['u'] <= 1.05 and abs(v['signed']) <= near_radius]
        # Signs either side, with chronological samples and bounded frame gap.
        spans = 0
        for old, new in zip(values, values[1:]):
            if 0 < new['frame'] - old['frame'] <= max_gap_frames and \
               old['signed'] * new['signed'] < 0 and \
               -0.05 <= old['u'] <= 1.05 and -0.05 <= new['u'] <= 1.05 and \
               max(abs(old['signed']),abs(new['signed'])) <= near_radius * 2:
                spans += 1
        if not near and not spans:
            continue
        best = min(near or values, key=lambda v: (abs(v['signed']),abs(v['time']-case['time_s'])))
        candidates.append({
            'track_id': tid, 'label': best['label'],
            'raw_track_id': best.get('raw_track_id'),
            'closest_frame': best['frame'],
            'closest_time_s': round(best['time'],4),
            'min_gate_distance': round(abs(best['signed']),6),
            'gate_projection': round(best['u'],4),
            'near_frame_count': len(near),
            'candidate_spans': spans,
        })
    candidates.sort(key=lambda x:(-int(x['candidate_spans']>0),x['min_gate_distance'],abs(x['closest_time_s']-case['time_s']),x['track_id']))
    result = dict(case)
    result.update(
        gate_observation_count=observed,
        unique_track_count=len(tracks),
        near_gate_tracks=len(candidates),
        finite_segment_span_candidates=sum(v['candidate_spans'] for v in candidates),
        nearest_tracks=candidates[:6],
        track_candidates_truncated=max(0,len(candidates)-6),
        scope='observed_bbox_geometry_only',
        physical_identity_proven=False,
        auto_recount_permitted=False,
    )
    return result


def build_report(export: Path, *, window: float = 1.0, near_radius: float = .035) -> dict:
    if not _finite_number(window) or not 0.1 <= window <= 2.0:
        raise ValueError('Window must be finite and between 0.1 and 2 seconds')
    if not _finite_number(near_radius) or not 0 < near_radius <= .1:
        raise ValueError('Near radius must be in (0, 0.1]')
    integrity = _verify(export)
    with ZipFile(export) as z:
        score=json.loads(z.read('report.json'))
        miss=score['missed_items']; extra=score['false_positive_items']
        raw_cases=[{'kind':'missed','case_id':v['ground_truth_id'], 'time_s':float(v['time']),
                    'direction':v['direction'], 'vehicle_type':v['vehicle_type']} for v in miss]
        raw_cases += [{'kind':'extra','case_id':v['ai_event_id'],'time_s':float(v['time']),
                       'direction':v['direction'],'vehicle_type':v['vehicle_type']} for v in extra]
        ids=[(c['kind'], c['case_id']) for c in raw_cases]
        if len(ids)!=len(set(ids)) or len(miss)!=integrity['missed'] or len(extra)!=integrity['extra']:
            raise ValueError('Report case integrity mismatch')
        for c in raw_cases:
            if not _finite_number(c['time_s']) or c['time_s'] < 0:
                raise ValueError('Invalid case time')
        raw_cases.sort(key=lambda c:(c['time_s'],c['kind']))
        observations=[[] for _ in raw_cases]
        geometry=None
        last_frame=0
        with z.open('benchmark-trace.jsonl.gz') as compressed, gzip.open(compressed,'rt',encoding='utf-8') as stream:
            for line in stream:
                d=json.loads(line)
                if d.get('kind')=='geometry_metadata':
                    geometry=d
                    continue
                if 'frame_index' not in d:
                    continue
                frame=int(d['frame_index'])
                if frame<=last_frame:
                    raise ValueError('Non-monotonic trace frames')
                last_frame=frame
                time=float(d['source_time_seconds'])
                targets=[i for i,c in enumerate(raw_cases) if abs(c['time_s']-time)<=window]
                if not targets:
                    continue
                if not geometry:
                    raise ValueError('Missing gate geometry')
                line_points=geometry['line']
                width=int(geometry['frame_width']);height=int(geometry['frame_height'])
                for row in d.get('gate_tracks',[]):
                    if not isinstance(row,dict):
                        continue
                    tid=row.get('track_id'); pt=row.get('anchor'); center=row.get('center')
                    if isinstance(tid,bool) or not isinstance(tid,int):
                        continue
                    # Prefer anchor, which owns the crossing decision. Center is
                    # only used when the anchor is unavailable.
                    measured=point_gate_geometry(pt if pt is not None else center,line_points,width,height)
                    if measured is None:
                        continue
                    u,signed=measured
                    # Reject positions wildly outside the processed frame.
                    if not (-.5<=u<=1.5 and abs(signed)<=.3):
                        continue
                    record={'track_id':tid,'raw_track_id':row.get('raw_track_id'),
                            'label':row.get('label'),'frame':frame,'time':time,'u':u,'signed':signed}
                    for idx in targets:
                        observations[idx].append(record)
    result=[case_witnesses(c,items,near_radius=near_radius) for c,items in zip(raw_cases,observations)]
    return {
        'format':'traffic-ai-verified-gate-coverage', 'version':1,
        'benchmark_id':integrity['benchmark_id'],'session_id':integrity['session_id'],
        'ground_truth_total':integrity['ground_truth_total'], 'ai_total':integrity['ai_total'],
        'matched':integrity['matched'], 'missed':integrity['missed'], 'extra':integrity['extra'],
        'verified_trace_sha256':integrity['source_trace_sha256'],
        'window_seconds':window,'near_gate_radius_normalized':near_radius,
        'frame_count_verified':last_frame, 'cases':result,
        'disclaimer':'Geometry-only review. An observed span is not a validated crossing or physical identity. No event/GT/score edits.'
    }


def write_report(report: dict, folder: Path) -> None:
    folder.mkdir(parents=True,exist_ok=True)
    (folder/'gate-coverage.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    headings=['time_s','kind','case_id','direction','vehicle_type','near_gate_tracks','finite_segment_span_candidates','unique_track_count','nearest_track_id','nearest_distance','nearest_projection']
    with (folder/'gate-coverage.csv').open('w',encoding='utf-8-sig',newline='') as dest:
        writer=csv.DictWriter(dest,fieldnames=headings);writer.writeheader()
        for item in report['cases']:
            top=item['nearest_tracks'][0] if item['nearest_tracks'] else {}
            writer.writerow({**{k:item[k] for k in headings[:8]},
                'nearest_track_id':top.get('track_id'),'nearest_distance':top.get('min_gate_distance'),
                'nearest_projection':top.get('gate_projection')})
    md=[f'# Gate coverage audit — Benchmark #{report["benchmark_id"]} / Session #{report["session_id"]}',
        '',f'GT {report["ground_truth_total"]} | AI {report["ai_total"]} | matched {report["matched"]} | missed {report["missed"]} | extra {report["extra"]}',
        '',f'Window ±{report["window_seconds"]:.2f}s; normalized gate radius {report["near_gate_radius_normalized"]:.3f}.',
        '', '**Read-only evidence: do NOT automatically count, suppress or edit GT.**','',
        '| Time | Kind | Case | Near tracks | Span candidates | Nearest track / distance |',
        '|---:|---|---:|---:|---:|---|']
    for row in report['cases']:
        top=row['nearest_tracks'][0] if row['nearest_tracks'] else None
        neighbor=f'{top["track_id"]} / {top["min_gate_distance"]:.4f}' if top else 'none'
        md.append(f'| {row["time_s"]:.3f} | {row["kind"]} | {row["case_id"]} | {row["near_gate_tracks"]} | {row["finite_segment_span_candidates"]} | {neighbor} |')
    md +=['','Span candidates are unverified geometric signs, NOT crossing events or same-vehicle matches. Review original clip before changing inference policy.','']
    (folder/'gate-coverage.md').write_text('\n'.join(md),encoding='utf-8')


def main(argv=None) -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--export',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,default=Path('gate-coverage-audit'))
    p.add_argument('--window',type=float,default=1.0)
    p.add_argument('--near-radius',type=float,default=.035)
    args=p.parse_args(argv)
    try:
        report=build_report(args.export,window=args.window,near_radius=args.near_radius)
        write_report(report,args.output_dir)
    except (OSError,ValueError,KeyError,TypeError,OverflowError,EOFError,json.JSONDecodeError) as exc:
        print(f'[ERROR] Verified gate coverage aborted: {exc}',file=sys.stderr)
        return 2
    print(f'Benchmark #{report["benchmark_id"]} / Session #{report["session_id"]}: {len(report["cases"])} gate cases, {report["frame_count_verified"]} frames verified')
    print(f'Reports: {args.output_dir}')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
