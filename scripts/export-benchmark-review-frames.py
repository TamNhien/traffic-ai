#!/usr/bin/env python3
"""V0.5.112: export verified, review-only error frames from the original video.

Neither scoring nor detector output is modified. No generated frame is a
training negative/positive label until a human reviews it.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path


def verified_cases(archive: Path) -> tuple[dict, dict, list[dict]]:
    path = Path(__file__).with_name('benchmark-forensics.py')
    spec = importlib.util.spec_from_file_location('traffic_benchmark_review_verifier', path)
    if not spec or not spec.loader:
        raise ValueError('Verified benchmark reader is not available')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    evidence = mod.analyze(archive, margin=1.25)
    if not evidence.get('trace_available'):
        raise ValueError('Benchmark lacks a complete, verified trace')
    from zipfile import ZipFile
    with ZipFile(archive) as z:
        report = json.loads(z.read('report.json'))
        config = json.loads(z.read('config.json'))
    if not report.get('ready') or report.get('session_id') != evidence.get('session_id'):
        raise ValueError('Benchmark report and verified trace session disagree')
    misses = [dict(kind='missed', time_s=float(c['time']), case_id=int(c['ground_truth_id']),
                   direction=c['direction'], vehicle_type=c['vehicle_type'])
              for c in report.get('missed_items', [])]
    extras = [dict(kind='extra', time_s=float(c['time']), case_id=int(c['ai_event_id']),
                   direction=c['direction'], vehicle_type=c['vehicle_type'])
              for c in report.get('false_positive_items', [])]
    cases = sorted(misses + extras, key=lambda x: (x['time_s'], x['kind']))
    if len(cases) != report.get('missed', -1) + report.get('false_positives', -1):
        raise ValueError('Unmatched case count disagrees with verified report')
    if not cases or any(not math.isfinite(x['time_s']) or x['time_s'] < 0 for x in cases):
        raise ValueError('Invalid or empty review queue')
    if len({(x['kind'], x['case_id']) for x in cases}) != len(cases):
        raise ValueError('Duplicate review case ID')
    return evidence, config, cases


def review_indices(time_s: float, fps: float, frame_count: int, *, half_window=0.4, step=0.2) -> list[int]:
    if not all(math.isfinite(v) for v in (time_s, fps, half_window, step)) or fps <= 0 or frame_count < 1:
        raise ValueError('Invalid video clock')
    if not (0 <= half_window <= 2.0 and 0.04 <= step <= 0.5):
        raise ValueError('Unsafe review window/step')
    if time_s < 0 or time_s > (frame_count - 1) / fps + .5:
        raise ValueError('Review event time outside video')
    count = math.floor((2 * half_window) / step + 1e-9)
    if count > 100:
        raise ValueError('Too many review samples')
    offsets = [-half_window + i * step for i in range(count + 1)]
    offsets.append(0.0)
    return sorted(set(max(0, min(frame_count - 1, int(round((time_s + delta) * fps)))) for delta in offsets))


def verify_video_metrics(*, actual_fps: float, actual_count: int, actual_width: int,
                         actual_height: int, expected_fps: float, expected_count: int,
                         trace_width: int, trace_height: int):
    vals = [actual_fps, expected_fps]
    if (not all(math.isfinite(v) for v in vals) or actual_fps <= 0 or expected_fps <= 0
        or abs(actual_fps - expected_fps) > .02 or abs(actual_count - expected_count) > 2
        or min(actual_width, actual_height, trace_width, trace_height) <= 0):
        raise ValueError('Original video does not match verified trace FPS/frame count')
    ratio = actual_width / actual_height
    trace_ratio = trace_width / trace_height
    if abs(ratio - trace_ratio) > .012:
        raise ValueError('Video aspect ratio differs from verified source')


def export_frames(archive: Path, video: Path, out: Path, *, expected_session: int | None = None,
                  half_window: float = .4, step: float = .2) -> dict:
    evidence, config, cases = verified_cases(archive)
    session_id = int(evidence['session_id'])
    if expected_session is not None and int(expected_session) != session_id:
        raise ValueError(f'Expected session #{expected_session}, got #{session_id}')
    if not video.is_file():
        raise FileNotFoundError(f'Original video not found: {video.resolve()}')
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError('OpenCV is required; run via scripts/export-benchmark-review-frames.ps1') from exc
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError('Cannot open original video')
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        nframes = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        # Read trace geometry *verified as part of the archive*, never a camera
        # geometry that might have changed in the live database.
        from zipfile import ZipFile
        import gzip
        with ZipFile(archive) as z, gzip.GzipFile(fileobj=z.open('benchmark-trace.jsonl.gz')) as stream:
            metadata = json.loads(stream.readline())
            geometry = json.loads(stream.readline())
        if metadata.get('kind') != 'session_metadata' or metadata.get('session_id') != session_id:
            raise ValueError('Verified trace session metadata is missing')
        if geometry.get('kind') != 'geometry_metadata' or geometry.get('session_id') != session_id:
            raise ValueError('Verified trace geometry is missing')
        verify_video_metrics(actual_fps=fps, actual_count=nframes,
            actual_width=width, actual_height=height,
            expected_fps=float(metadata['source_fps']), expected_count=int(metadata['source_frame_count']),
            trace_width=int(geometry['source_frame_width']), trace_height=int(geometry['source_frame_height']))
        line = config['benchmark_snapshot']['geometry']
        a = (int(line['line_x1'] * width), int(line['line_y1'] * height))
        b = (int(line['line_x2'] * width), int(line['line_y2'] * height))
        # Stage preflight completely before writing any output. The output
        # must not overwrite existing files or masquerade as an earlier audit.
        if out.exists() and any(out.iterdir()):
            raise ValueError(f'Output directory is not empty: {out}')
        out.mkdir(parents=True, exist_ok=True)
        records = []
        for case in cases:
            indices = review_indices(case['time_s'], fps, nframes,half_window=half_window,step=step)
            folder = out / f"{case['kind']}_{case['case_id']}_{case['time_s']:.3f}s"
            folder.mkdir(exist_ok=False)
            frames = []
            for frame_idx in indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ok, frame = cap.read()
                if not ok or frame is None:
                    raise ValueError(f'Unable to decode original video frame {frame_idx}')
                cv2.line(frame, a, b, (0, 255, 255), max(2, width // 700))
                caption = f"{case['kind'].upper()} #{case['case_id']} | video {frame_idx/fps:.3f}s | {case['direction']}"
                cv2.putText(frame,caption,(14,36),cv2.FONT_HERSHEY_SIMPLEX, .8,(255,255,255),2)
                if width > 1440:
                    scale = 1440 / width
                    frame = cv2.resize(frame,(1440,int(round(height*scale))))
                fname = f'frame_{frame_idx+1:06d}.jpg'
                if not cv2.imwrite(str(folder/fname), frame, [cv2.IMWRITE_JPEG_QUALITY, 89]):
                    raise OSError(f'Unable to save frame {fname}')
                frames.append({'frame_index': frame_idx+1,'source_time_s': round(frame_idx/fps, 5),
                               'file': f'{folder.name}/{fname}'})
            records.append({**case,'frames':frames})
        report = {'format':'traffic-ai-review-frame-pack','schema_version':1,
                  'benchmark_id':evidence['benchmark_id'],'session_id':session_id,
                  'source_fps':fps,'source_frames':nframes,
                  'verified_trace_sha256':evidence.get('source_trace_sha256'),
                  'label_status':'UNREVIEWED — NOT training annotations',
                  'scoring_modified':False,'cases':records}
        (out/'review-manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (out/'README.md').write_text(
            f'# Review frames — Benchmark #{report["benchmark_id"]} / Session #{session_id}\n\n'
            f'{len(records)} unmatched cases, {sum(len(r["frames"]) for r in records)} video frames.\n\n'
            'Each image is a candidate for **manual** review, not a verified detection or a YOLO training label.\n'
            'Confirm vehicle identity, crossing direction, and GT timing in the original continuous video.\n'
            'Do not mark empty frames as negative examples without manual inspection.\n',encoding='utf-8')
        return report
    finally:
        cap.release()


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--export',type=Path,required=True)
    p.add_argument('--video',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--expected-session',type=int)
    p.add_argument('--half-window',type=float,default=.4)
    p.add_argument('--step',type=float,default=.2)
    a=p.parse_args(argv)
    try:
        r=export_frames(a.export,a.video,a.output_dir,expected_session=a.expected_session,
                        half_window=a.half_window,step=a.step)
    except (OSError,RuntimeError,ValueError,KeyError,TypeError) as e:
        print(f'[ERROR] Review frame export: {e}',file=sys.stderr)
        return 2
    print(f'Benchmark #{r["benchmark_id"]} / Session #{r["session_id"]}: '
          f'{len(r["cases"])} cases, {sum(len(x["frames"]) for x in r["cases"])} review frames')
    print(f'Saved {a.output_dir}')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
