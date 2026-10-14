#!/usr/bin/env python3
"""Verified, read-only review queue for every unmatched GT/AI crossing.

Time-neighbor suggestions are not physical-vehicle identity evidence.  A full
scored export is required; this utility never edits GT or AI event records.
"""
from __future__ import annotations

import argparse
import csv
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent


def load_script(name: str):
    spec = spec_from_file_location('traffic_' + name.replace('-', '_'), ROOT / (name + '.py'))
    if spec is None or spec.loader is None:
        raise ValueError('Missing source verifier: ' + name)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def seconds(row: dict) -> float:
    return float(row['time'])


def timecode(t: float) -> str:
    ms = round(t * 1000)
    mins, rem = divmod(ms, 60_000)
    hours, mins = divmod(mins, 60)
    return f'{hours:02d}:{mins:02d}:{rem // 1000:02d}.{rem % 1000:03d}'


def build_queue(archive: Path, *, near_window: float | None = None) -> dict:
    compare = load_script('compare-benchmark-exports')
    verified = compare._read_evidence(archive)  # validates JSON and closed trace hashes
    if not verified['scored']:
        raise ValueError('Hồ sơ chưa có GT hoặc chưa chấm điểm. Hãy tải lại ZIP sau khi sao chép GT.')
    r = verified['report']
    tol = float(r['tolerance_seconds'])
    window = tol if near_window is None else float(near_window)
    if not 0 < window <= 3:
        raise ValueError('Review window must be between 0 and 3 seconds')

    misses = r['missed_items']
    extras = r['false_positive_items']
    rows = []
    for i, item in enumerate(misses, 1):
        evidence = item.get('temporal_evidence') or {}
        is_competing = evidence.get('status') == 'persisted_event_claimed_by_other_gt'
        label = 'GT gần AI đã ghép GT khác' if is_competing else 'GT chưa có AI tương ứng'
        evidence_scope = (item.get('diagnosis') or {}).get('diagnosis_scope', {})
        claimed = (item.get('matching_audit') or {}).get('nearby_matched_events') or []
        rows.append({
            'case_id': f'GT-{i:02}', 'kind': 'missed', 'time_seconds': seconds(item),
            'timecode': timecode(seconds(item)), 'direction': str(item.get('direction', '')).upper(),
            'vehicle_type': item.get('vehicle_type'), 'classification': label,
            'reason': (item.get('diagnosis') or {}).get('reason') or 'review_video',
            'temporal_status': evidence.get('status'),
            'evidence_scope': evidence_scope.get('geometry'),
            'nearby_assigned_ai_event_ids': [e.get('ai_event_id') for e in claimed[:5]],
            'nearby_assigned_gt_ids': [e.get('assigned_ground_truth_id') for e in claimed[:5]],
            'nearby_opposite_case_ids': [],
            'review_action': 'Kiểm tra hai xe riêng biệt, vạch và thứ tự ghép GT/AI' if is_competing
                             else 'Kiểm tra detection/tracking và Gate ở từng frame',
            'identity_proven': False,
        })
    for i, item in enumerate(extras, 1):
        rows.append({
            'case_id': f'AI-{i:02}', 'kind': 'extra', 'time_seconds': seconds(item),
            'timecode': timecode(seconds(item)), 'direction': str(item.get('direction', '')).upper(),
            'vehicle_type': item.get('vehicle_type'),
            'classification': 'AI chưa có mốc GT ghép',
            'reason': item.get('reason') or 'review_video',
            'crossing_method': item.get('crossing_method'),
            'near_matched_time_delta': item.get('near_matched_time_delta'),
            'near_matched_spatial_distance': item.get('near_matched_spatial_distance'),
            'near_matched_ai_event_id': item.get('near_matched_ai_event_id'),
            'nearby_opposite_case_ids': [],
            'review_action': 'Kiểm tra một xe hay nhiều xe trong video; không tự xóa AI',
            'identity_proven': False,
        })
    # Allow human reviewer to navigate nearby GT/AI candidates, with no inferred
    # identity, automatic reclassification, or report score changes.
    for row in rows:
        alternate = 'extra' if row['kind'] == 'missed' else 'missed'
        neighbors = [other for other in rows if other['kind'] == alternate
                     and abs(other['time_seconds'] - row['time_seconds']) <= window]
        row['nearby_opposite_case_ids'] = [x['case_id'] for x in sorted(
            neighbors, key=lambda x: (abs(x['time_seconds'] - row['time_seconds']), x['case_id']))]
    rows.sort(key=lambda x: (x['time_seconds'], x['case_id']))
    summary = {
        'format': 'traffic-ai-verified-error-review-queue', 'schema_version': 1,
        'session_id': r['session_id'], 'benchmark_id': r['benchmark']['id'],
        'ground_truth_total': r['ground_truth_total'], 'ai_total': r['ai_total'],
        'matched': r['matched'], 'missed': r['missed'], 'extra': r['false_positives'],
        'tolerance_seconds': tol, 'review_window_seconds': window,
        'temporal_conflict_missed': sum(bool((item.get('temporal_evidence') or {}).get('status') ==
                                               'persisted_event_claimed_by_other_gt') for item in misses),
        'near_matched_extra': sum(item.get('near_matched_ai_event_id') is not None for item in extras),
        'case_count': len(rows),
        'evidence_note': 'Near-time matching does NOT prove identity, duplicate count, or true detection miss.',
        'cases': rows,
    }
    return summary


def as_markdown(data: dict) -> str:
    lines = [f'# Danh sách cần kiểm tra · Benchmark #{data["benchmark_id"]} / Session #{data["session_id"]}', '',
             f'GT **{data["ground_truth_total"]}**, AI **{data["ai_total"]}**, khớp **{data["matched"]}**, '
             f'lọt **{data["missed"]}**, dư **{data["extra"]}**.', '',
             f'- GT có AI gần đó nhưng đã ghép GT khác: **{data["temporal_conflict_missed"]}**.',
             f'- AI dư gần một AI đã khớp: **{data["near_matched_extra"]}**.',
             '- Lọc theo timecode chỉ để điều hướng; không chứng minh hai xe là một.', '',
             '| Timecode | Loại | Hướng | Xe | Nguyên nhân quan sát | Mốc đối diện gần |',
             '|---|---|---|---|---|---|']
    for row in data['cases']:
        lines.append(f'| {row["timecode"]} | {row["case_id"]} | {row["direction"]} | '
                     f'{row["vehicle_type"]} | {str(row["reason"]).replace("|", "/")} | '
                     f'{", ".join(row["nearby_opposite_case_ids"]) or "—"} |')
    lines.extend(['', '**Chú ý:** Hãy đối chiếu từng trường hợp với video gốc và GT đã duyệt '
                  'trước khi sửa thuật toán. Báo cáo không làm thay đổi điểm số hoặc cơ sở dữ liệu.', ''])
    return '\n'.join(lines)


def write_queue(data: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir/'review-queue.json').write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (output_dir/'review-queue.md').write_text(as_markdown(data), encoding='utf-8')
    columns = ['case_id', 'kind', 'time_seconds', 'timecode', 'direction', 'vehicle_type',
               'classification', 'reason', 'temporal_status', 'crossing_method',
               'near_matched_time_delta', 'near_matched_spatial_distance', 'near_matched_ai_event_id',
               'nearby_assigned_ai_event_ids', 'nearby_assigned_gt_ids',
               'nearby_opposite_case_ids', 'review_action']
    with (output_dir/'review-queue.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        for row in data['cases']:
            row = {**row, 'nearby_opposite_case_ids': ', '.join(row['nearby_opposite_case_ids']),
                   'nearby_assigned_ai_event_ids': ', '.join(str(v) for v in row.get('nearby_assigned_ai_event_ids', [])),
                   'nearby_assigned_gt_ids': ', '.join(str(v) for v in row.get('nearby_assigned_gt_ids', []))}
            writer.writerow(row)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Verified read-only benchmark error review queue')
    parser.add_argument('--export', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        data = build_queue(args.export)
        write_queue(data, args.output_dir)
        print(f'Benchmark #{data["benchmark_id"]} / Session #{data["session_id"]}: '
              f'GT {data["ground_truth_total"]}, AI {data["ai_total"]}, '
              f'lọt {data["missed"]}, dư {data["extra"]}, review {data["case_count"]}')
        print(f'Đã xuất review-queue.csv / .json / .md: {args.output_dir.resolve()}')
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f'[ERROR] Không thể xuất review queue: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
