#!/usr/bin/env python3
"""V0.5.115: overlay verified *observations*, never inferred vehicle identities.

Consumes the already-exported review-frame directory and its original benchmark.
Original JPEGs, DB events, GT and benchmark ZIP are never written or relabeled.
"""
from __future__ import annotations

import argparse
import gzip
import importlib.util
import json
import math
import sys
import zipfile
from pathlib import Path


def _review_tool():
    path = Path(__file__).with_name('export-benchmark-review-frames.py')
    spec = importlib.util.spec_from_file_location('traffic_review_export_v05115', path)
    if spec is None or spec.loader is None:
        raise ValueError('Verified review-frame dependency is missing')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _safe_jpeg(base: Path, name: str) -> Path:
    if not isinstance(name, str) or not name or '\\' in name:
        raise ValueError('Unsafe or missing review JPEG path')
    rel = Path(name)
    if rel.is_absolute() or '..' in rel.parts or rel.suffix.lower() != '.jpg':
        raise ValueError('Review JPEG path escapes input directory')
    resolved = (base / rel).resolve()
    if not resolved.is_relative_to(base.resolve()) or not resolved.is_file():
        raise ValueError('Review JPEG is missing or points outside input directory')
    return resolved


def validate_review_manifest(manifest: dict, evidence: dict, cases: list[dict], base: Path) -> dict[int, list[tuple[dict,dict]]]:
    if not isinstance(manifest, dict) or manifest.get('format') != 'traffic-ai-review-frame-pack' or manifest.get('schema_version') != 1:
        raise ValueError('Invalid review-frame manifest format')
    if (manifest.get('session_id') != evidence.get('session_id') or
        manifest.get('benchmark_id') != evidence.get('benchmark_id') or
        manifest.get('verified_trace_sha256') != evidence.get('source_trace_sha256')):
        raise ValueError('Review frames do not belong to this verified benchmark/trace')
    if manifest.get('scoring_modified') is not False or manifest.get('source_fps', 0) <= 0:
        raise ValueError('Review-frame manifest is missing read-only provenance')
    expected = {(c['kind'], int(c['case_id'])) for c in cases}
    supplied = manifest.get('cases')
    if not isinstance(supplied, list) or len(supplied) != len(expected):
        raise ValueError('Review case count does not match benchmark')
    refs: dict[int, list[tuple[dict,dict]]] = {}
    seen = set()
    image_paths = set()
    for case in supplied:
        if not isinstance(case, dict):
            raise ValueError('Malformed review case')
        key = (case.get('kind'), case.get('case_id'))
        if key not in expected or key in seen:
            raise ValueError('Missing, duplicate or foreign review case')
        seen.add(key)
        frames = case.get('frames')
        if not isinstance(frames, list) or not (1 <= len(frames) <= 100):
            raise ValueError('Invalid number of frames in review case')
        if not math.isfinite(float(case.get('time_s', float('nan')))):
            raise ValueError('Invalid review timecode')
        for item in frames:
            if not isinstance(item, dict) or type(item.get('frame_index')) is not int:
                raise ValueError('Invalid review frame index')
            idx = item['frame_index']
            if idx < 1 or idx > manifest.get('source_frames', 0):
                raise ValueError('Review frame outside video bounds')
            if not math.isfinite(float(item.get('source_time_s', float('nan')))) or abs(float(item['source_time_s']) - (idx - 1)/float(manifest['source_fps'])) > .06:
                raise ValueError('Review frame timecode disagrees with source clock')
            source = _safe_jpeg(base, item.get('file'))
            if item['file'] in image_paths and not source.is_file():
                raise ValueError('Review image missing')
            image_paths.add(item['file'])
            refs.setdefault(idx, []).append((case, item))
    if len(refs) > 1000:
        raise ValueError('Review contains too many unique frame indices')
    return refs


def verified_trace_frames(archive: Path, wanted: set[int], session_id: int) -> tuple[dict, dict[int,dict]]:
    """One streaming pass, bounded retention: never load the 413 MB trace in RAM."""
    found = {}
    geometry = None
    with zipfile.ZipFile(archive) as z, gzip.GzipFile(fileobj=z.open('benchmark-trace.jsonl.gz')) as f:
        meta = json.loads(f.readline())
        geometry = json.loads(f.readline())
        if (meta.get('kind') != 'session_metadata' or meta.get('session_id') != session_id or
            geometry.get('kind') != 'geometry_metadata' or geometry.get('session_id') != session_id):
            raise ValueError('Trace session/geometry metadata mismatch')
        for line in f:
            row = json.loads(line)
            idx = row.get('frame_index')
            if idx in wanted:
                if idx in found or not isinstance(row.get('gate_tracks'), list):
                    raise ValueError('Duplicate or missing trace track observations')
                found[idx] = row
    if set(found) != wanted:
        raise ValueError(f'Trace missing {len(wanted-set(found))} selected review frames')
    if min(geometry.get('frame_width',0), geometry.get('frame_height',0)) <= 0:
        raise ValueError('Invalid trace frame dimensions')
    return geometry, found


def _dist_to_gate(rect: list, line: list) -> float:
    x1,y1,x2,y2 = (float(x) for x in rect)
    if not all(math.isfinite(x) for x in (x1,y1,x2,y2)):
        return float('inf')
    px, py = (x1+x2)/2, y2
    (ax,ay),(bx,by) = line
    d2 = (bx-ax)**2 + (by-ay)**2
    if d2 < 1e-8:
        return float('inf')
    t = max(0., min(1., ((px-ax)*(bx-ax)+(py-ay)*(by-ay))/d2))
    return math.hypot(px-(ax+t*(bx-ax)),py-(ay+t*(by-ay)))


def bounded_track_annotations(row: dict, geometry: dict, *, limit: int = 10) -> list[dict]:
    fw,fh=geometry['frame_width'],geometry['frame_height']
    line = [[p[0]*fw,p[1]*fh] for p in geometry['line']]
    tracks = []
    for t in row.get('gate_tracks', []):
        if not isinstance(t,dict) or not isinstance(t.get('rect'),list) or len(t['rect'])!=4:
            continue
        rect=t['rect']
        try:
            dist=_dist_to_gate(rect,line)
        except (TypeError,ValueError):
            continue
        if not math.isfinite(dist) or not isinstance(t.get('track_id'),int):
            continue
        status = str(t.get('final_gate_decision') or t.get('primary_gate_decision') or 'unrecorded')[:70]
        tracks.append({'track_id':t['track_id'],'raw_track_id':t.get('raw_track_id'),
          'vehicle_type':str(t.get('label','unknown'))[:32],
          'rect':[round(float(v),3) for v in rect],
          'decision':status,'distance_px':round(dist,2),
          'human_guard_status':str(t.get('human_guard_status') or 'unrecorded')[:40]})
    tracks.sort(key=lambda v: (v['distance_px'],v['track_id']))
    return tracks[:limit]


def _paint(cv2, frame, tracks: list[dict], geometry: dict, case: dict, index: int):
    h,w=frame.shape[:2]
    sx=w/geometry['frame_width']; sy=h/geometry['frame_height']
    line=geometry['line']
    a=(int(line[0][0]*w),int(line[0][1]*h))
    b=(int(line[1][0]*w),int(line[1][1]*h))
    cv2.line(frame,a,b,(0,220,255),max(2,w//700))
    cv2.putText(frame,f"TRACE OBSERVATIONS ONLY | {case['kind']} #{case['case_id']} | frame {index}",
                (12,28),cv2.FONT_HERSHEY_SIMPLEX,.63,(255,255,255),2)
    for t in tracks:
        x1,y1,x2,y2=t['rect']
        aa=(max(0,min(w-1,int(x1*sx))),max(0,min(h-1,int(y1*sy))))
        bb=(max(0,min(w-1,int(x2*sx))),max(0,min(h-1,int(y2*sy))))
        status=t['decision']
        color=(60,210,60) if status == 'primary-accepted' else ((40,50,240) if ('suppress' in status or 'reject' in status) else (220,150,40))
        cv2.rectangle(frame,aa,bb,color,2)
        cv2.putText(frame,f"T{t['track_id']} {t['vehicle_type']} | {status}",
                    (aa[0],max(47,aa[1]-5)),cv2.FONT_HERSHEY_SIMPLEX,.45,color,1)
    cv2.putText(frame,'Track decisions are NOT GT identity or confirmed physical passage',
                (12,h-14),cv2.FONT_HERSHEY_SIMPLEX,.54,(255,255,255),2)


def annotate(archive: Path, review_dir: Path, out: Path, *, expected_session: int | None = None) -> dict:
    if out.resolve() == review_dir.resolve() or out.resolve().is_relative_to(review_dir.resolve()):
        raise ValueError('Output must be separate from original review frames')
    if out.exists() and any(out.iterdir()):
        raise ValueError('Output directory is not empty; use a new directory')
    import cv2
    tool=_review_tool()
    evidence, _config, cases = tool.verified_cases(archive)
    if expected_session is not None and evidence.get('session_id') != expected_session:
        raise ValueError('Expected session does not match benchmark')
    manifest=json.loads((review_dir/'review-manifest.json').read_text(encoding='utf-8'))
    requested=validate_review_manifest(manifest,evidence,cases,review_dir)
    geometry,frame_data=verified_trace_frames(archive,set(requested),evidence['session_id'])
    out.mkdir(parents=True,exist_ok=True)
    rendered=[]
    for idx in sorted(requested):
        selected=bounded_track_annotations(frame_data[idx],geometry)
        for case,item in requested[idx]:
            src=_safe_jpeg(review_dir,item['file'])
            image=cv2.imread(str(src))
            if image is None or image.shape[0]<24 or image.shape[1]<24:
                raise ValueError('Cannot decode original review JPEG')
            _paint(cv2,image,selected,geometry,case,idx)
            dst=out/item['file']; dst.parent.mkdir(parents=True,exist_ok=True)
            if not cv2.imwrite(str(dst),image,[cv2.IMWRITE_JPEG_QUALITY,90]):
                raise OSError('Failed to save review overlay')
            rendered.append({'case_kind':case['kind'],'case_id':case['case_id'],
                             'frame_index':idx,'file':item['file'],'trace_tracks':selected,
                             'road_tracks':frame_data[idx].get('road_tracks'),
                             'road_margin_eligible_tracks':frame_data[idx].get('road_margin_eligible_tracks'),
                             'near_gate_eligible_tracks':frame_data[idx].get('near_gate_eligible_tracks')})
    result={'format':'traffic-ai-review-track-overlay','schema_version':1,
      'session_id':evidence['session_id'],'benchmark_id':evidence['benchmark_id'],
      'verified_trace_sha256':evidence['source_trace_sha256'],
      'image_count':len(rendered),'case_count':len(cases),
      'labels_are_ground_truth':False,'scoring_modified':False,
      'warning':'Observed tracks and primary decisions are not validated physical identity or vehicle counts',
      'frames':rendered}
    (out/'trace-overlay.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (out/'README.md').write_text(
      f'# Track overlay — Benchmark #{result["benchmark_id"]} / Session #{result["session_id"]}\n\n'
      f'{result["case_count"]} cases, {result["image_count"]} annotated JPEGs.\n\n'
      '**Unreviewed observation only.** Trace bounding boxes, IDs, and decisions are not proof of GT identity.\n'
      'Original review JPEGs and benchmark remain unchanged. No labels or counts were edited.\n',encoding='utf-8')
    bundle=out/'review-tracks-upload.zip'
    with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
        for p in sorted(out.rglob('*')):
            if p.is_file() and p != bundle:
                z.write(p,p.relative_to(out).as_posix())
    result['bundle']=str(bundle)
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--export',type=Path,required=True)
    p.add_argument('--review-dir',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--expected-session',type=int)
    a=p.parse_args(argv)
    try:
        r=annotate(a.export,a.review_dir,a.output_dir,expected_session=a.expected_session)
    except (OSError,RuntimeError,ValueError,KeyError,TypeError,zipfile.BadZipFile) as e:
        print(f'[ERROR] Track review overlay: {e}',file=sys.stderr)
        return 2
    print(f'Benchmark #{r["benchmark_id"]} / Session #{r["session_id"]}: '
          f'{r["case_count"]} cases, {r["image_count"]} annotated frames')
    print(f'Upload ZIP: {r["bundle"]}')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
