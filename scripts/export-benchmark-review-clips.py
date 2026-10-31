#!/usr/bin/env python3
"""V0.5.133: continuous, read-only video evidence around verified GT/AI review cases.

This tool is NOT an inference engine or automatic correction. Matching clip metadata
and hashing video bytes do not prove its physical identity against an older session.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent
KINDS = (('missed', 'missed_items', 'missed'),
         ('extra', 'false_positive_items', 'false_positives'),
         ('direction', 'direction_mismatch_items', 'direction_mismatches'),
         ('class', 'class_mismatch_items', 'class_mismatches'))
MAX_CASES = 100
MAX_VIDEO_BYTES = 30 * 1024 ** 3


def module(filename, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    if not spec or not spec.loader:
        raise ValueError(f'Missing local verifier: {filename}')
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


compare = module('compare-benchmark-exports.py', 'clip_compare_v05133')
quality = module('audit-benchmark-quality.py', 'clip_quality_v05133')


def positive_number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f'Invalid {name}')
    return float(value)


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read_cases(archive: Path):
    # Existing verifier checks the declared SHA256 for ALL benchmark ZIP members.
    verified = compare._read_evidence(archive)
    report = verified['report']
    benchmark = report['benchmark']
    session = report['session_id']
    if not isinstance(session, int) or isinstance(session, bool) or session <= 0:
        raise ValueError('Missing or invalid session ID')
    if not report.get('ready') or benchmark.get('session_id') != session:
        raise ValueError('Not a scored benchmark for this session')
    fps = positive_number(benchmark.get('source_fps'), 'source FPS')
    duration = positive_number(benchmark.get('source_duration_seconds'), 'source duration')
    if fps > 240 or duration > 24 * 3600:
        raise ValueError('Unsupported source video dimensions')
    with ZipFile(archive) as z, gzip.GzipFile(fileobj=z.open('benchmark-trace.jsonl.gz')) as stream:
        meta = json.loads(stream.readline())
        geometry = json.loads(stream.readline())
    if (meta.get('kind') != 'session_metadata' or meta.get('session_id') != session or
        geometry.get('kind') != 'geometry_metadata' or geometry.get('session_id') != session):
        raise ValueError('Verified trace metadata does not match the reported session')
    source_fps = positive_number(meta.get('source_fps'), 'trace FPS')
    if abs(source_fps - fps) > .001:
        raise ValueError('Trace/report FPS mismatch')
    nframes = meta.get('source_frame_count')
    if not isinstance(nframes, int) or isinstance(nframes, bool) or nframes < 1 or abs(nframes / fps - duration) > .25:
        raise ValueError('Trace/report frame count or duration mismatch')
    w, h = geometry.get('source_frame_width'), geometry.get('source_frame_height')
    if any(not isinstance(n, int) or isinstance(n, bool) or n < 32 or n > 16384 for n in (w, h)):
        raise ValueError('Invalid source video dimensions in verified trace')
    cases = []
    for kind, key, countkey in KINDS:
        items = report.get(key)
        count = report.get(countkey)
        if not isinstance(items, list) or not isinstance(count, int) or len(items) != count:
            raise ValueError('Incomplete reported review cases: ' + kind)
        for item in items:
            record = quality._issue(kind, item)
            seconds = record['time']
            if isinstance(seconds, bool) or not isinstance(seconds, (float, int)) or not math.isfinite(seconds) or not 0 <= seconds <= duration:
                raise ValueError('Invalid review event timecode')
            cases.append(record)
    if not cases or len(cases) > MAX_CASES:
        raise ValueError('Invalid number of review cases')
    cases.sort(key=lambda c: (c['time'], c['kind'], str(c.get('ai_event_id'))))
    for i, record in enumerate(cases, 1):
        record['review_id'] = f'REVIEW-{i:02d}'
    return {'session_id':session,'benchmark_id':benchmark['id'],'fps':fps,
            'duration':duration,'frames':nframes,'width':w,'height':h,
            'source_basename':Path(str(benchmark['source_url']).replace('\\','/')).name,
            'cases':cases,'archive_sha256':sha256(archive)}


def groups(cases, duration, half_window):
    """Merge overlapping windows to avoid duplicating clips for crowded moments."""
    result = []
    for case in cases:
        start = max(0., case['time'] - half_window)
        end = min(duration, case['time'] + half_window)
        if end - start < .04:
            raise ValueError('Review window lies outside source')
        if result and start <= result[-1]['end'] and end - result[-1]['start'] <= 16.:
            result[-1]['end'] = max(end, result[-1]['end'])
            result[-1]['case_ids'].append(case['review_id'])
        else:
            result.append({'start':start,'end':end,'case_ids':[case['review_id']]})
    for i, g in enumerate(result, 1):
        g['clip_id'] = f'CLIP-{i:02d}'
        g['filename'] = f'clip_{i:02d}_{g["start"]:08.3f}s.mp4'
        g['start'] = round(g['start'], 3)
        g['end'] = round(g['end'], 3)
    return result


def probe_video(video, runner=subprocess.run):
    cmd = ['ffprobe','-v','error','-select_streams','v:0','-show_entries',
           'stream=codec_type,width,height,avg_frame_rate,nb_frames:format=duration',
           '-of','json',str(video)]
    result = runner(cmd, capture_output=True, text=True, timeout=40, check=True)
    info = json.loads(result.stdout)
    streams = info.get('streams') or []
    if len(streams) != 1:
        raise ValueError('Expected exactly one primary video stream')
    stream = streams[0]
    fps_text = stream.get('avg_frame_rate')
    if not isinstance(fps_text, str) or '/' not in fps_text:
        raise ValueError('Unsupported video frame rate')
    a,b = fps_text.split('/',1)
    fps = positive_number(float(a), 'video FPS numerator') / positive_number(float(b), 'video FPS denominator')
    dur = positive_number(float(info['format']['duration']), 'video duration')
    n = stream.get('nb_frames')
    frame_count = int(n) if isinstance(n, str) and n.isdecimal() else None
    return {'fps':fps,'duration':dur,'width':stream['width'],'height':stream['height'],'frames':frame_count}


def verify_video(recorded, probed, video):
    # Basename prevents accidental cross-camera review; media metadata alone is
    # still not a cryptographic identity proof against a historical clip.
    if video.name != recorded['source_basename']:
        raise ValueError(f'Video filename does not match verified benchmark source ({recorded["source_basename"]})')
    if (abs(probed['fps'] - recorded['fps']) > .025 or
        abs(probed['duration'] - recorded['duration']) > .25 or
        probed['width'] != recorded['width'] or probed['height'] != recorded['height']):
        raise ValueError('Video FPS/duration/resolution differs from verified benchmark trace')
    if probed['frames'] is not None and abs(probed['frames'] - recorded['frames']) > 2:
        raise ValueError('Video frame count differs from verified benchmark trace')


def render(archive:Path, video:Path, output:Path, *, expected_session:int|None=None,
           half_window=2.0, runner=subprocess.run):
    if not isinstance(half_window, (int,float)) or isinstance(half_window,bool) or not math.isfinite(half_window) or not .25 <= half_window <= 4.0:
        raise ValueError('Half-window must be 0.25–4 seconds')
    if not archive.is_file() or archive.is_symlink() or not video.is_file() or video.is_symlink():
        raise ValueError('Benchmark ZIP and original video must be regular local files')
    if video.stat().st_size < 100 or video.stat().st_size > MAX_VIDEO_BYTES:
        raise ValueError('Source video is empty or exceeds the 30 GiB limit')
    record = read_cases(archive)
    if expected_session is not None and expected_session != record['session_id']:
        raise ValueError('Expected session does not match verified archive')
    data = probe_video(video,runner)
    verify_video(record,data,video)
    clips = groups(record['cases'],record['duration'],float(half_window))
    source_sha256_before = sha256(video)
    out = output.resolve()
    for input_path in (video.resolve(),archive.resolve()):
        if out == input_path or out in input_path.parents or input_path in out.parents:
            raise ValueError('Output must not contain or be contained by source files')
    if output.is_symlink() or (output.exists() and (not output.is_dir() or any(output.iterdir()))):
        raise ValueError('Output directory must be new or empty; existing review is protected')
    # Do not make visible partial evidence. Stage first and publish manifest last.
    output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.review-pending-',dir=output) as td:
        stage=Path(td)
        for clip in clips:
            name=stage / clip['filename']
            length=round(clip['end']-clip['start'],3)
            cmd=['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-threads','2',
                 '-ss',f'{clip["start"]:.3f}','-i',str(video),'-t',f'{length:.3f}',
                 '-map','0:v:0','-vf',"scale='min(1280,iw)':-2",
                 '-c:v','libx264','-preset','veryfast','-crf','25',
                 '-pix_fmt','yuv420p','-an','-movflags','+faststart',
                 '-y',str(name)]
            runner(cmd, capture_output=True, text=True, timeout=180, check=True)
            if not name.is_file() or name.stat().st_size < 200:
                raise ValueError('Empty or incomplete generated review clip')
            encoded = probe_video(name, runner)
            if abs(encoded['duration'] - length) > .55 or abs(encoded['fps']-record['fps']) > .10:
                raise ValueError('Output clip length/FPS does not match requested source window')
            clip['sha256'] = sha256(name)
            clip['size_bytes'] = name.stat().st_size
        if sha256(video) != source_sha256_before:
            raise ValueError('Source video changed during export; refusing evidence manifest')
        result={'format':'traffic-ai-verified-continuous-review','schema_version':1,
                'benchmark_id':record['benchmark_id'],'session_id':record['session_id'],
                'benchmark_zip_sha256':record['archive_sha256'],
                'video_sha256':source_sha256_before,'source_video_name':video.name,
                'video_metadata':data,'camera_source_identity_proven':False,
                'cases':record['cases'],'clips':clips,
                'counts_or_ground_truth_modified':False,
                'labels_generated':False,
                'note':'Read-only review candidates. Source metadata and SHA256 bind the selected local file, but do not prove it is the exact historical video. Review visually; no automatic GT/AI changes.'}
        (stage/'review-clips.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        with (stage/'review-clips.csv').open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.writer(f);writer.writerow(['clip_id','filename','start_seconds','end_seconds','review_ids'])
            for clip in clips:
                writer.writerow([clip['clip_id'],clip['filename'],clip['start'],clip['end'],','.join(clip['case_ids'])])
        lines=[f'# Continuous video review — Benchmark #{record["benchmark_id"]} / Session #{record["session_id"]}',
               '',f'{len(record["cases"])} issues grouped into {len(clips)} continuous MP4 clips.',
               'Review only; not training labels, not GT corrections, not AI fixes.','',
               '| Clip | Video clock (s) | Cases | SHA-256 |','|---|---|---|---|']
        for clip in clips:
            lines.append(f'| {clip["filename"]} | {clip["start"]:.3f}–{clip["end"]:.3f} | {", ".join(clip["case_ids"])} | `{clip["sha256"]}` |')
        lines += ['','The original source must be checked by a human. Identical FPS/resolution/duration does NOT prove video identity.','']
        (stage/'review-clips.md').write_text('\n'.join(lines),encoding='utf-8')
        for file in stage.iterdir():
            if file.name != 'review-clips.json':
                file.rename(output/file.name)
        (stage/'review-clips.json').rename(output/'review-clips.json')
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--export',type=Path,required=True)
    p.add_argument('--video',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--expected-session',type=int)
    p.add_argument('--half-window',default=2.0,type=float)
    args=p.parse_args(argv)
    try:
        r=render(args.export,args.video,args.output_dir,expected_session=args.expected_session,half_window=args.half_window)
    except (OSError,ValueError,KeyError,TypeError,RuntimeError,subprocess.SubprocessError,OverflowError) as exc:
        print('[FAIL] Video review export: '+str(exc),file=sys.stderr)
        return 2
    print(f'[OK] Benchmark #{r["benchmark_id"]} / Session #{r["session_id"]}: {len(r["cases"])} cases, {len(r["clips"])} review MP4s.')
    print('[OK] Verified ZIP; source video metadata checked; no production data modified.')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
