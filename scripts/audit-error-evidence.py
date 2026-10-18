#!/usr/bin/env python3
"""V0.5.99 - verified, read-only passage evidence worklist.

Do not reinterpret timestamp-nearby events as the same physical vehicle.
The original matcher result, GT and database events are never modified.
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

FRAME_RE = re.compile(r'(?:^|_)frame_(\d+)\.jpe?g$', re.I)
MAX_IMAGES = 5000
MAX_IMAGE_GAP_SECONDS = 1.0


def _forensics():
    path = Path(__file__).with_name('benchmark-forensics.py')
    spec = importlib.util.spec_from_file_location('traffic_verified_benchmark_forensics_599', path)
    if spec is None or spec.loader is None:
        raise ValueError('Missing verified benchmark-forensics verifier')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _image_index(folder: Path | None) -> list[tuple[int, str]]:
    if folder is None:
        return []
    if not folder.is_dir():
        raise ValueError('Camera images must be an extracted directory of JPG files')
    images = []
    # Non-recursive and bounded, never follow symlinks out of the evidence folder.
    for path in folder.iterdir():
        if path.is_symlink() or not path.is_file():
            continue
        match = FRAME_RE.search(path.name)
        if match:
            if not (0 < int(match[1]) <= 1_000_000_000):
                continue
            images.append((int(match[1]), path.name))
            if len(images) > MAX_IMAGES:
                raise ValueError('Too many camera images (limit 5000)')
    return sorted(images)


def _timecode(seconds: float) -> str:
    if not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds < 0:
        raise ValueError('Invalid source timecode')
    ms = round(seconds * 1000)
    hrs, remaining = divmod(ms, 3_600_000)
    mins, remaining = divmod(remaining, 60_000)
    return f'{hrs:02d}:{mins:02d}:{remaining // 1000:02d}.{remaining % 1000:03d}'


def _classify(case: dict) -> tuple[str, str]:
    """A triage status is a review hypothesis, NEVER an identity verdict."""
    if case['kind'] == 'missed':
        status = (case.get('report_evidence') or {}).get('status')
        if status == 'persisted_event_claimed_by_other_gt':
            return ('temporal_assignment_conflict',
                    'Rà GT khác đang giữ AI gần timecode; đối chiếu hai phương tiện trên video.')
        return ('unmatched_gt_without_available_event',
                'Kiểm tra detection, track, hướng và bằng chứng qua vạch ở video gốc.')
    candidate = case.get('review_candidate') or {}
    reason = case.get('diagnostic_reason') or 'review_video'
    if reason == 'spatial_duplicate_near_gt':
        return ('spatial_neighbor_review',
                'Rà 2 bounding box/track cùng lúc, không tự xóa một lượt.')
    if reason == 'rescued_gap_unmatched':
        return ('gap_rescue_review',
                'Rà ảnh trước/sau gap, ID thay đổi và hướng chuyển động.')
    if reason in ('direct_unmatched', 'interpolated_unmatched'):
        return ('unmatched_crossing_review',
                'Xác nhận xe thực sự cắt vạch và có/không có mốc GT trong video.')
    if candidate:
        return ('nearby_event_review', 'Rà cặp event gần nhau; không suy ra cùng xe.')
    return ('unmatched_crossing_review', 'Rà lượt AI chưa khớp với video gốc.')


def make_worklist(forensics: dict, images: list[tuple[int, str]] | None = None,
                  source_fps: float | None = None) -> dict:
    """Pure review classification from *verified* forensics results."""
    if forensics.get('format') != 'traffic-ai-gt-case-forensics' or not forensics.get('trace_available'):
        raise ValueError('A verified, complete benchmark trace is required')
    cases = forensics.get('cases')
    if not isinstance(cases, list) or len(cases) > 100_000:
        raise ValueError('Invalid or oversized case list')
    if sum(c.get('kind') == 'missed' for c in cases) != forensics.get('missed') or \
       sum(c.get('kind') == 'extra' for c in cases) != forensics.get('extra'):
        raise ValueError('Matcher case counts are inconsistent')
    if images and (not isinstance(source_fps, (int, float)) or
                   not math.isfinite(source_fps) or source_fps <= 0):
        raise ValueError('A verified positive source FPS is required to attach camera images')
    images = images or []
    result = []
    counts = {}
    for i, case in enumerate(sorted(cases, key=lambda x: (x['time'], x['kind']))):
        category, action = _classify(case)
        counts[category] = counts.get(category, 0) + 1
        evidence = case.get('trace_evidence') or {}
        source_time = float(case['time'])
        if not math.isfinite(source_time) or source_time < 0:
            raise ValueError('Invalid source time')
        photo = None
        photo_delta_seconds = None
        if images:
            # Frame indexes in the camera RAR are 1-based, source seconds are 0-based.
            expected_frame = round(source_time * source_fps) + 1
            frame, name = min(images, key=lambda item: (abs(item[0] - expected_frame), item[0]))
            gap = abs(frame - expected_frame) / source_fps
            if gap <= MAX_IMAGE_GAP_SECONDS:
                photo = name
                photo_delta_seconds = round(gap, 3)
        report_evidence = case.get('report_evidence') or {}
        nearby_assigned = report_evidence.get('nearby_persisted_events') or []
        # A frame showing anchors on both sides is NOT sufficient to prove a crossing.
        tracks = evidence.get('tracks') or {}
        crossing_candidates = [
            {'track_id': k, 'observations': v.get('samples'),
             'near_line_samples': v.get('near_line_samples'),
             'observed_both_sides': bool(v.get('side_negative') and v.get('side_positive'))}
            for k, v in tracks.items() if v.get('near_line_samples', 0) > 0
        ][:8]
        row = {
            'case_id': f'{"GT" if case["kind"] == "missed" else "AI"}-{i+1:02d}',
            'kind': case['kind'], 'time': source_time, 'timecode': _timecode(source_time),
            'direction': case.get('direction'), 'vehicle_type': case.get('vehicle_type'),
            'ground_truth_id': case.get('ground_truth_id'), 'ai_event_id': case.get('ai_event_id'),
            'category': category, 'review_action': action,
            'report_reason': case.get('diagnostic_reason') if case['kind'] == 'extra' else None,
            'temporal_status': report_evidence.get('status'),
            'nearby_assigned_event_ids': [v.get('ai_event_id') for v in nearby_assigned[:8]],
            'nearby_assigned_gt_ids': [v.get('assigned_ground_truth_id') for v in nearby_assigned[:8]],
            'frames_in_window': evidence.get('frames', 0),
            'tracked_both_sides': evidence.get('tracks_both_sides', 0),
            'near_line_tracks': evidence.get('near_line_tracks', 0),
            'candidate_tracks': crossing_candidates,
            'nearby_proposals': (evidence.get('proposals') or [])[:20],
            'nearby_deliveries': (evidence.get('deliveries') or [])[:20],
            'camera_image': photo, 'camera_image_time_offset_seconds': photo_delta_seconds,
            'physical_identity_proven': False,
        }
        result.append(row)
    return {
        'format': 'traffic-ai-passage-evidence-worklist', 'schema_version': 1,
        'version': '0.5.99',
        'session_id': forensics['session_id'], 'benchmark_id': forensics['benchmark_id'],
        'ground_truth_total': forensics['ground_truth_total'],
        'ai_total': forensics['ai_total'], 'matched': forensics['matched'],
        'missed': forensics['missed'], 'extra': forensics['extra'],
        'case_count': len(result), 'category_counts': dict(sorted(counts.items())),
        'verified_trace_sha256': forensics['source_trace_sha256'],
        'source_fps': source_fps,
        'limitations': [
            'No event/GT is added, deleted, reclassified or rematched.',
            'Nearby-in-time, tracked-both-sides, or nearby image alone does not prove physical vehicle identity.',
            'Missing in matcher does not necessarily mean missing in detector.',
            'Camera JPG is a snapshot only; review the original MP4 for crossing direction and identity.',
        ],
        'cases': result,
    }


def as_markdown(result: dict) -> str:
    lines = [f'# Passage evidence audit - Benchmark #{result["benchmark_id"]} / Session #{result["session_id"]}',
             '', f'GT **{result["ground_truth_total"]}** | AI **{result["ai_total"]}** | '
             f'Matched **{result["matched"]}** | Missed **{result["missed"]}** | Extra **{result["extra"]}**',
             '', f'Verified trace SHA256: `{result["verified_trace_sha256"]}`', '',
             '## Diagnostic categories (review hypotheses; no automatic correction)', '']
    for name, count in result['category_counts'].items():
        lines.append(f'- `{name}`: **{count}**')
    lines.extend(['', '## Review sequence', '',
                  '| Timecode | Kind | GT/AI ID | Direction | Vehicle | Category | Camera JPG |',
                  '|---|---|---|---|---|---|---|'])
    for row in result['cases']:
        rid = row['ground_truth_id'] if row['kind'] == 'missed' else row['ai_event_id']
        lines.append(f'| {row["timecode"]} | {row["kind"]} | {rid} | {row["direction"]} | '
                     f'{row["vehicle_type"]} | `{row["category"]}` | '
                     f'{row["camera_image"] or "none within 1s"} |')
    lines.extend(['', '## Case evidence', ''])
    for row in result['cases']:
        lines.extend([f'### {row["case_id"]} at {row["timecode"]}', '',
                      f'- **Action:** {row["review_action"]}',
                      f'- Temporal matcher: `{row["temporal_status"]}`; report reason: `{row["report_reason"]}`',
                      f'- Assigned nearby AI IDs: {row["nearby_assigned_event_ids"]}; '
                      f'GT IDs: {row["nearby_assigned_gt_ids"]}',
                      f'- Trace: {row["frames_in_window"]} frames; {row["near_line_tracks"]} near-line IDs; '
                      f'{row["tracked_both_sides"]} IDs sampled on both sides; '
                      f'{len(row["nearby_proposals"])} nearby proposals; '
                      f'{len(row["nearby_deliveries"])} nearby delivery receipts.', ''])
    lines.extend(['## Interpretation', ''] + ['- ' + statement for statement in result['limitations']] + [''])
    return '\n'.join(lines)


def save(result: dict, folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder/'passage-evidence.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (folder/'passage-evidence.md').write_text(as_markdown(result), encoding='utf-8')
    columns = ('case_id', 'timecode', 'kind', 'direction', 'vehicle_type', 'ground_truth_id',
               'ai_event_id', 'category', 'report_reason', 'temporal_status',
               'frames_in_window', 'near_line_tracks', 'tracked_both_sides', 'camera_image',
               'camera_image_time_offset_seconds', 'review_action')
    with (folder/'passage-evidence.csv').open('w', newline='', encoding='utf-8-sig') as fp:
        writer = csv.DictWriter(fp, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        for row in result['cases']:
            writer.writerow(row)


def _verified_source_fps(archive: Path) -> float:
    # The session.json is integrity-checked by benchmark-gate via forensics.analyze.
    from zipfile import ZipFile
    with ZipFile(archive) as z:
        data = json.loads(z.read('session.json'))
    value = data.get('source_fps')
    if isinstance(value, bool) or not isinstance(value, (int, float)) or \
       not math.isfinite(value) or value <= 0 or value > 1000:
        raise ValueError('No finite source FPS in the verified session snapshot')
    return float(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export', type=Path, required=True, help='Full verified benchmark export ZIP')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--camera-images', type=Path, help='Optional extracted JPG directory (not the RAR itself)')
    parser.add_argument('--window', type=float, default=1.0, help='Evidence window in seconds, 0.1..5')
    args = parser.parse_args(argv)
    try:
        proof = _forensics().analyze(args.export, margin=args.window)
        imgs = _image_index(args.camera_images)
        fps = _verified_source_fps(args.export) if imgs else None
        result = make_worklist(proof, imgs, fps)
        save(result, args.output_dir)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f'[FAIL] Verified passage audit: {exc}', file=sys.stderr)
        return 2
    print(f'[OK] Benchmark #{result["benchmark_id"]} / Session #{result["session_id"]}: '
          f'{result["missed"]} GT missed + {result["extra"]} AI extra; '
          f'{result["case_count"]} verified review cases.')
    print(f'[OK] Evidence: {args.output_dir / "passage-evidence.md"}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
