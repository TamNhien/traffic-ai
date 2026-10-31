#!/usr/bin/env python3
"""V0.5.132 local-only: pair verified benchmark review cases with session-scoped JPEGs.

Only visual navigation evidence. A nearby JPG is not proof of identity, a vehicle
crossing, an incorrect model decision, or a license to change GT/counts.
"""
from __future__ import annotations
import argparse
import csv
import importlib.util
import json
import math
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parent
PAT = re.compile(r'^session_(\d+)(?:_.*)?_frame_(\d+)\.jpe?g$', re.I)
MAX_IMAGES = 5000
MAX_IMAGE_BYTES = 6 * 1024 * 1024
MAX_CASES = 1000

def _module(filename: str, label: str):
    spec = importlib.util.spec_from_file_location(label, ROOT / filename)
    if spec is None or spec.loader is None:
        raise ValueError('Missing verification dependency: ' + filename)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

quality = _module('audit-benchmark-quality.py', 'camera_quality_132')
compare = _module('compare-benchmark-exports.py', 'camera_compare_132')

CATEGORIES = (('missed', 'missed_items', 'missed'),
              ('extra', 'false_positive_items', 'false_positives'),
              ('direction', 'direction_mismatch_items', 'direction_mismatches'),
              ('class', 'class_mismatch_items', 'class_mismatches'))

def camera_index(folder: Path, session_id: int) -> dict[int, Path]:
    if not folder.is_dir() or folder.is_symlink():
        raise ValueError('Camera folder must be an extracted local directory, not a RAR or symlink')
    found = {}
    examined = 0
    foreign = 0
    for path in folder.iterdir():
        if path.is_symlink() or not path.is_file():
            continue
        m = PAT.fullmatch(path.name)
        if not m:
            continue
        examined += 1
        if examined > MAX_IMAGES:
            raise ValueError('Too many JPEG files; review the camera directory')
        if int(m.group(1)) != session_id:
            foreign += 1
            continue
        frame = int(m.group(2))
        if frame <= 0 or frame > 1_000_000_000:
            raise ValueError('Invalid recorded frame number')
        if frame in found:
            raise ValueError('Multiple JPEG candidates for the same session/frame; cannot choose safely')
        if path.stat().st_size > MAX_IMAGE_BYTES or path.stat().st_size < 4:
            raise ValueError('Suspicious camera JPEG size: ' + path.name)
        with path.open('rb') as fp:
            if fp.read(3) != b'\xff\xd8\xff':
                raise ValueError('Camera file does not have JPEG signature: ' + path.name)
        found[frame] = path
    if not found:
        raise ValueError(f'No JPEG for Session #{session_id}; {foreign} files from other sessions ignored')
    return found

def analyze(archive: Path, camera_folder: Path, max_gap_seconds: float = 0.8) -> dict:
    if isinstance(max_gap_seconds, bool) or not isinstance(max_gap_seconds, (float, int)) or not math.isfinite(max_gap_seconds) or not .04 <= max_gap_seconds <= 2.0:
        raise ValueError('Maximum camera gap must be between 0.04 and 2.0 seconds')
    verified = compare._read_evidence(archive)  # validates every declared ZIP-member SHA-256
    report = verified['report']
    benchmark = report['benchmark']
    session = report['session_id']
    if not isinstance(session, int) or isinstance(session, bool) or session <= 0:
        raise ValueError('Invalid benchmark session')
    fps = benchmark.get('source_fps')
    if isinstance(fps, bool) or not isinstance(fps, (int, float)) or not math.isfinite(fps) or not 0 < fps <= 240:
        raise ValueError('Invalid recorded FPS')
    indexed = camera_index(camera_folder, session)
    frames = sorted(indexed)
    issues = []
    for kind, field, count in CATEGORIES:
        items = report.get(field)
        if not isinstance(items, list) or len(items) != report.get(count) or len(items) + len(issues) > MAX_CASES:
            raise ValueError('Incomplete or inconsistent scored issue list: ' + field)
        for item in items:
            c = quality._issue(kind, item)
            c['expected_frame'] = round(c['time'] * fps) + 1
            closest = min(frames, key=lambda n: (abs(n-c['expected_frame']), n))
            gap = abs(closest - c['expected_frame']) / fps
            c['nearest_frame'] = closest
            c['frame_gap_seconds'] = round(gap, 3)
            c['camera_status'] = 'nearby_snapshot' if gap <= max_gap_seconds else 'insufficient_frame_coverage'
            c['camera_filename'] = indexed[closest].name if gap <= max_gap_seconds else None
            c['camera_session_verified'] = True
            c['identity_proven'] = False
            c['original_video_required'] = True
            issues.append(c)
    issues.sort(key=lambda c:(c['time'],c['kind'],str(c.get('ai_event_id'))))
    for i, issue in enumerate(issues, 1):
        issue['review_id'] = f'REVIEW-{i:02d}'
    return {'format':'traffic-ai-verified-camera-evidence','schema_version':1,
            'benchmark_id':benchmark['id'], 'session_id':session,'fps':fps,
            'max_gap_seconds':max_gap_seconds,'verified_benchmark_sha256':True,
            'camera_images_matching_session':len(indexed),
            'issues':issues,
            'summary':{'issues':len(issues),'nearby_snapshots':sum(x['camera_status']=='nearby_snapshot' for x in issues),
                       'insufficient_coverage':sum(x['camera_status']!='nearby_snapshot' for x in issues)},
            'read_only':True, 'counting_modified':False, 'gt_modified':False,
            'warnings':['Camera images are diagnostic snapshots and are not verified by the benchmark manifest.',
                        'A nearby frame is not continuous evidence, cannot prove vehicle identity and is not a counting fix.',
                        'Frame number and session are checked; image content requires human review against the original MP4.',
                        'No benchmark, Ground Truth, database, inference settings or production events were changed.']}

def write_outputs(result:dict, source:Path, output:Path, *, include_images:bool = True):
    if output.exists() and any(output.iterdir()):
        raise ValueError('Output folder must be empty or new; refusing to overwrite prior review')
    if output.is_symlink() or source.resolve() == output.resolve() or source.resolve() in output.resolve().parents:
        raise ValueError('Output cannot be the camera folder or a subdirectory of it')
    output.mkdir(parents=True, exist_ok=True)
    photos = output/'evidence'
    if include_images:photos.mkdir()
    for c in result['issues']:
        c['evidence_file'] = None
        name = c.get('camera_filename')
        if include_images and name:
            src = source/name
            if src.is_symlink() or not src.is_file() or src.stat().st_size > MAX_IMAGE_BYTES:
                raise ValueError('Camera image changed during audit')
            dst = photos/(c['review_id']+'_'+name)
            shutil.copyfile(src,dst)
            c['evidence_file'] = 'evidence/'+dst.name
    (output/'camera-review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    columns=('review_id','kind','timecode','ground_truth_id','ai_event_id','tracking_id','ground_truth_direction',
             'ai_direction','ground_truth_class','ai_class','crossing_method','audit_reason','expected_frame',
             'nearest_frame','frame_gap_seconds','camera_status','camera_filename','evidence_file','review_action')
    with (output/'camera-review.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');w.writeheader();w.writerows(result['issues'])
    s=result['summary']
    lines=[f'# Benchmark #{result["benchmark_id"]} / Session #{result["session_id"]} — camera evidence review',
           '',f'- Review: **{s["issues"]}**; nearby JPG: **{s["nearby_snapshots"]}**, no sufficiently close JPG: **{s["insufficient_coverage"]}**.',
           '- Read-only, session-scoped; no automatic GT or AI corrections.','',
           '| Review | Time | Type | Gap (s) | Evidence status |','|---|---|---|---:|---|']
    for c in result['issues']:
        lines.append(f'| {c["review_id"]} | {c["timecode"]} | {c["kind"]} | {c["frame_gap_seconds"]:.3f} | {c["camera_status"]} |')
    lines.extend(['','## Cautions',*(f'- {x}' for x in result['warnings']),''])
    (output/'camera-review.md').write_text('\n'.join(lines),encoding='utf-8')

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--export',required=True,type=Path)
    p.add_argument('--camera-folder',required=True,type=Path)
    p.add_argument('--output-dir',required=True,type=Path)
    p.add_argument('--max-gap-seconds',default=0.8,type=float)
    p.add_argument('--no-copy-images',action='store_true')
    args=p.parse_args(argv)
    try:
        data=analyze(args.export,args.camera_folder,args.max_gap_seconds)
        write_outputs(data,args.camera_folder,args.output_dir,include_images=not args.no_copy_images)
    except (OSError,RuntimeError,ValueError,TypeError,KeyError,json.JSONDecodeError) as e:
        print('[FAIL] Camera evidence audit: '+str(e),file=sys.stderr)
        return 2
    s=data['summary']
    print(f'[OK] Benchmark #{data["benchmark_id"]} / Session #{data["session_id"]}: {s["issues"]} issues; {s["nearby_snapshots"]} nearby JPEG; {s["insufficient_coverage"]} insufficient.')
    print('[OK] Ground Truth and production events unchanged. Saved '+str(args.output_dir))
    return 0

if __name__=='__main__':raise SystemExit(main())
