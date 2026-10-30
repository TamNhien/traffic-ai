#!/usr/bin/env python3
"""V0.5.126: read-only, integrity-verified GT/AI review of ALL error categories.

Never treat a timestamp-nearby event, an image or opposite-side track samples
as a proof of the same physical vehicle. No ground truth or events are mutated.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import re
import sys
from pathlib import Path
from zipfile import ZipFile

IMAGE_PATTERN = re.compile(r'(?:^|_)frame_(\d+)\.jpe?g$', re.I)
MAX_IMAGES = 5000
MAX_ISSUES = 10000


def _load_forensics():
    path = Path(__file__).with_name('benchmark-forensics.py')
    spec = importlib.util.spec_from_file_location('traffic_benchmark_quality_forensics_126', path)
    if spec is None or spec.loader is None:
        raise ValueError('Verified benchmark forensics not present')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _camera_index(directory: Path | None) -> list[tuple[int, str]]:
    if directory is None:
        return []
    if not directory.is_dir():
        raise ValueError('CameraImages must be an extracted JPG directory, not a RAR file')
    items = []
    for path in directory.iterdir():
        if not path.is_file() or path.is_symlink():
            continue
        match = IMAGE_PATTERN.search(path.name)
        if match:
            idx = int(match[1])
            if 0 < idx < 1_000_000_000:
                items.append((idx, path.name))
                if len(items) > MAX_IMAGES:
                    raise ValueError('Camera directory exceeds image index limit')
    return sorted(items)


def _finite_time(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError('Benchmark issue has invalid source time')
    return float(value)


def _fmt_time(t: float) -> str:
    millis = round(t * 1000)
    hr, rest = divmod(millis, 3600000)
    mn, rest = divmod(rest, 60000)
    return f'{hr:02d}:{mn:02d}:{rest // 1000:02d}.{rest % 1000:03d}'


def _issue(kind: str, entry: dict) -> dict:
    if kind in ('missed', 'extra'):
        t = _finite_time(entry.get('time'))
    else:
        t = _finite_time(entry.get('time'))
    gt = entry.get('ground_truth_id')
    ai = entry.get('ai_event_id')
    if kind == 'missed':
        hint = (entry.get('temporal_evidence') or {}).get('status', 'no_verified_event')
        action = ('Compare multiple vehicles around the same time; nearby AI is assigned to another GT.'
                  if hint == 'persisted_event_claimed_by_other_gt' else
                  'Review original video and trace for detection, track and gate crossing.')
    elif kind == 'extra':
        hint = entry.get('reason', 'unmatched_event')
        action = ('Inspect both track identities and the entire passage; proximity does not prove a duplicate.'
                  if hint == 'spatial_duplicate_near_gt' else
                  'Check original video and contiguous raw motion before changing crossing policy.')
    elif kind == 'direction':
        hint = 'time_matched_direction_conflict'
        action = 'Inspect original MP4 for two distinct vehicles and actual IN/OUT at the line.'
    else:
        hint = 'time_matched_class_conflict'
        action = 'Inspect original MP4, class-refinement evidence and annotated identity before relabeling.'
    return {
        'kind': kind, 'time': t, 'timecode': _fmt_time(t),
        'ground_truth_id': gt, 'ai_event_id': ai,
        'tracking_id': entry.get('tracking_id') or entry.get('ai_tracking_id'),
        'ground_truth_direction': entry.get('ground_truth_direction', entry.get('direction') if kind == 'missed' else None),
        'ai_direction': entry.get('ai_direction', entry.get('direction') if kind == 'extra' else None),
        'ground_truth_class': entry.get('ground_truth_vehicle_type', entry.get('vehicle_type') if kind == 'missed' else None),
        'ai_class': entry.get('ai_vehicle_type', entry.get('vehicle_type') if kind == 'extra' else None),
        'crossing_method': entry.get('crossing_method'),
        'audit_reason': hint, 'review_action': action,
        'identity_proven': False,
    }


def analyze(export: Path, *, window: float = 1.0, camera_images: Path | None = None) -> dict:
    if isinstance(window, bool) or not isinstance(window, (int, float)) or not math.isfinite(window) or not 0.1 <= window <= 5:
        raise ValueError('Window must be finite and between 0.1 and 5 seconds')
    forensics = _load_forensics()
    report, manifest = forensics._verified_load(export)
    parts = [
        ('missed', 'missed_items', 'missed'),
        ('extra', 'false_positive_items', 'false_positives'),
        ('direction', 'direction_mismatch_items', 'direction_mismatches'),
        ('class', 'class_mismatch_items', 'class_mismatches'),
    ]
    cases = []
    for kind, name, count_key in parts:
        entries = report.get(name, [])
        if not isinstance(entries, list) or len(entries) != report.get(count_key):
            raise ValueError(f'Benchmark issue count mismatch: {name}')
        if len(entries) + len(cases) > MAX_ISSUES:
            raise ValueError('Too many review issues')
        cases.extend(_issue(kind, entry) for entry in entries)
    if len({(c['kind'], c['ground_truth_id'], c['ai_event_id']) for c in cases}) != len(cases):
        raise ValueError('Duplicate benchmark issue identity')
    fps = _finite_time(report['benchmark']['source_fps'])
    if fps <= 0 or fps > 1000:
        raise ValueError('Invalid recorded source FPS')
    images = _camera_index(camera_images)
    with ZipFile(export) as archive:
        trace = forensics._read_trace(archive, manifest, cases, window)
    if not trace.get('available'):
        raise ValueError(f'Complete verified trace required: {trace.get("reason")}')
    for index, case in enumerate(cases):
        evidence = trace['cases'][index]
        case['trace'] = {
            'frames_in_window': evidence['frames'],
            'tracks_observed_both_sides': evidence['tracks_both_sides'],
            'near_line_tracks': evidence['near_line_tracks'],
            'nearby_proposals': evidence['proposals'][:12],
            'nearby_deliveries': evidence['deliveries'][:12],
        }
        case['camera_image'] = None
        case['camera_gap_seconds'] = None
        if images:
            expected = round(case['time'] * fps) + 1
            actual, name = min(images, key=lambda entry: (abs(entry[0] - expected), entry[0]))
            gap = abs(actual - expected) / fps
            if gap <= 1.0:
                case['camera_image'] = name
                case['camera_gap_seconds'] = round(gap, 3)
    cases.sort(key=lambda c: (c['time'], c['kind'], str(c.get('ai_event_id'))))
    for i, case in enumerate(cases, 1):
        case['review_id'] = f'REVIEW-{i:02d}'
    return {
        'format': 'traffic-ai-benchmark-quality-audit', 'schema_version': 1,
        'benchmark_id': report['benchmark']['id'], 'session_id': report['session_id'],
        'gt': report['ground_truth_total'], 'ai': report['ai_total'],
        'matched': report['matched'], 'missed': report['missed'], 'extra': report['false_positives'],
        'direction_mismatches': report['direction_mismatches'],
        'class_mismatches': report['class_mismatches'],
        'review_count': len(cases), 'source_fps': fps, 'window_seconds': window,
        'trace_source_sha256': trace['source_sha256'],
        'camera_images_indexed': len(images),
        'read_only': True, 'accuracy_improvement_claimed': False,
        'warnings': [
            'A source-time match is not proof of the same physical vehicle.',
            'Camera JPEGs are snapshots; use the full original video to verify identity and direction.',
            'A track observed on both sides is only a review candidate, not permission to auto-count.',
            'Original benchmark GT/AI events and matching are not modified.'
        ],
        'issues': cases,
    }


def write_outputs(data: dict, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest/'benchmark-quality.json').write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    cols = ('review_id','timecode','kind','ground_truth_id','ai_event_id','tracking_id',
            'ground_truth_direction','ai_direction','ground_truth_class','ai_class',
            'crossing_method','audit_reason','camera_image','camera_gap_seconds','review_action')
    with (dest/'benchmark-quality.csv').open('w', newline='', encoding='utf-8-sig') as fp:
        writer = csv.DictWriter(fp, fieldnames=cols, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(data['issues'])


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--export', required=True, type=Path)
    p.add_argument('--output-dir', type=Path, default=Path('benchmark-quality-audit'))
    p.add_argument('--camera-images', type=Path, default=None)
    p.add_argument('--window', type=float, default=1.0)
    args = p.parse_args(argv)
    try:
        result = analyze(args.export, window=args.window, camera_images=args.camera_images)
        write_outputs(result, args.output_dir)
    except (ValueError, KeyError, TypeError, OSError, EOFError, RuntimeError, json.JSONDecodeError) as exc:
        print(f'[FAIL] Benchmark quality audit (read-only): {exc}', file=sys.stderr)
        return 2
    print(f'[OK] Benchmark #{result["benchmark_id"]} / Session #{result["session_id"]}: '
          f'GT {result["gt"]}, AI {result["ai"]}; '
          f'{result["missed"]} missed / {result["extra"]} extra / '
          f'{result["direction_mismatches"]} direction / {result["class_mismatches"]} class issues.')
    print(f'[OK] Verified SHA-256 trace; review {result["review_count"]} issues at {args.output_dir}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
