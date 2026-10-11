#!/usr/bin/env python3
"""Offline what-if eval of the production direct/direct ID-switch rule.

NEVER changes the benchmark, event DB, trained model or GT. GT is read only
by the evaluation scorer AFTER candidate removal decisions have been made.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import sys
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.benchmarking import match_crossings  # noqa: E402
from app.shadow_guard import direct_ultra_spatial_shadow_duplicate  # noqa: E402


class InvalidBenchmark(ValueError):
    pass


def _load_zip(path: Path) -> dict:
    if not path.is_file():
        raise InvalidBenchmark('Không tìm thấy hồ sơ benchmark.')
    with ZipFile(path) as z:
        if len(z.infolist()) > 30:
            raise InvalidBenchmark('ZIP chứa số lượng file không hợp lệ.')
        names = set(z.namelist())
        expected = {'manifest.json', 'report.json', 'ground-truth.json', 'events.json', 'session.json'}
        if not expected <= names:
            raise InvalidBenchmark('Thiếu manifest, report, GT, events hoặc session.')
        if z.getinfo('manifest.json').file_size > 200_000:
            raise InvalidBenchmark('Manifest quá lớn.')
        manifest = json.loads(z.read('manifest.json'))
        if manifest.get('format') != 'traffic-ai-benchmark-diagnostics':
            raise InvalidBenchmark('Định dạng hồ sơ không được hỗ trợ.')
        result = {}
        for name in ('report.json', 'ground-truth.json', 'events.json', 'session.json'):
            entry = (manifest.get('files') or {}).get(name) or {}
            member = z.getinfo(name)
            if member.file_size > 25_000_000 or member.file_size != entry.get('bytes'):
                raise InvalidBenchmark('Kích thước không hợp lệ: ' + name)
            content = z.read(name)
            if sha256(content).hexdigest() != entry.get('sha256'):
                raise InvalidBenchmark('SHA-256 không đúng: ' + name)
            result[name] = json.loads(content)
        if result['session.json'].get('status') != 'completed':
            raise InvalidBenchmark('Chỉ đánh giá phiên AI đã COMPLETED.')
        if result['session.json'].get('id') != manifest.get('session_id'):
            raise InvalidBenchmark('Session ID giữa manifest và dữ liệu không khớp.')
        if result['report.json'].get('session_id') != manifest.get('session_id'):
            raise InvalidBenchmark('Report không thuộc phiên được xuất.')
        return result


def _valid_crossing(e: dict) -> bool:
    return (isinstance(e.get('tracking_id'), int)
            and e.get('crossing_method') == 'direct'
            and isinstance(e.get('direction'), str)
            and isinstance(e.get('vehicle_type'), str)
            and all(isinstance(e.get(k), (int, float)) and math.isfinite(e[k]) for k in
                    ('source_time_seconds', 'crossing_x', 'crossing_y'))
            and 0 <= e['crossing_x'] <= 1 and 0 <= e['crossing_y'] <= 1)


def dedup_counterfactual(events: list[dict]) -> tuple[list[dict], list[dict]]:
    """Decide suppression using only AI events; never consult GT/report labels."""
    kept: list[dict] = []
    suppressed: list[dict] = []
    # Real backend can persist events in asynchronous source order; DB id is the
    # closest available proxy in a saved snapshot, not a full GPU replay.
    for event in sorted(events, key=lambda e: e['id']):
        previous = None
        if _valid_crossing(event):
            for other in reversed(kept):
                if not _valid_crossing(other):
                    continue
                if (other['tracking_id'] == event['tracking_id']
                    or other['direction'] != event['direction']
                    or other['vehicle_type'] != event['vehicle_type']):
                    continue
                dt = abs(event['source_time_seconds'] - other['source_time_seconds'])
                dist = math.hypot(event['crossing_x']-other['crossing_x'], event['crossing_y']-other['crossing_y'])
                if direct_ultra_spatial_shadow_duplicate(dt, dist,
                         event.get('crossing_method'), other.get('crossing_method')):
                    previous = other
                    break
        if previous is None:
            kept.append(event)
        else:
            suppressed.append({'removed_event_id': event['id'],
                'kept_event_id': previous['id'],
                'time_delta_seconds': round(abs(event['source_time_seconds'] - previous['source_time_seconds']), 4),
                'crossing_distance': round(math.hypot(event['crossing_x'] - previous['crossing_x'],
                                                     event['crossing_y'] - previous['crossing_y']), 6)})
    return kept, suppressed


def _metrics(report: dict) -> dict:
    return {k: report[k] for k in ('ground_truth_total', 'ai_total', 'matched', 'missed', 'false_positives',
                                   'counting_recall', 'counting_precision', 'counting_f1')}


def analyze(path: Path) -> dict:
    data = _load_zip(path)
    marks, events = data['ground-truth.json'], data['events.json']
    report = data['report.json']
    tolerance = float(report.get('tolerance_seconds', 0.75))
    if len(events) != report.get('ai_total') or len(marks) != report.get('ground_truth_total'):
        raise InvalidBenchmark('Báo cáo và số lượng GT/events không đồng nhất.')
    baseline = match_crossings(marks, events, tolerance)
    for k in ('matched', 'missed', 'false_positives'):
        if baseline[k] != report.get(k):
            raise InvalidBenchmark('Báo cáo không khớp khi chạy lại phép ghép thời gian: ' + k)
    after_events, suppressed = dedup_counterfactual(events)
    after = match_crossings(marks, after_events, tolerance)
    return {'session_id': report['session_id'],
            'disclaimer': 'Counterfactual dựa trên snapshot; không phải kết quả chạy lại GPU; không thay đổi dữ liệu thực.',
            'baseline': _metrics(baseline), 'counterfactual': _metrics(after),
            'suppressed_candidates': suppressed,
            'benchmark_score_uses_gt_only_after_decisions': True}


def main() -> int:
    ap = argparse.ArgumentParser(description='Evaluate bounded direct-shadow dedup from benchmark ZIP')
    ap.add_argument('--export', required=True)
    ap.add_argument('--output-dir', default='shadow-counterfactual-report')
    args = ap.parse_args()
    try:
        result = analyze(Path(args.export))
        dest = Path(args.output_dir)
        dest.mkdir(parents=True, exist_ok=True)
        (dest/'counterfactual.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
        b,a = result['baseline'],result['counterfactual']
        lines=['# Session #{0} — Direct Shadow Counterfactual'.format(result['session_id']),'',
               '**Đánh giá offline, không phải kết quả AI replay thực tế.**','',
               '| Chỉ số | Gốc | Giả định sau chống trùng |','|---|---:|---:|']
        for k,label in [('ground_truth_total','GT'),('ai_total','AI'),('matched','Khớp'),
                        ('missed','Lọt'),('false_positives','Dư')]:
            lines.append(f'| {label} | {b[k]} | {a[k]} |')
        lines += ['', '## Event dự kiến bị loại', '']
        for x in result['suppressed_candidates']:
            lines.append(f"- AI #{x['removed_event_id']} → giữ AI #{x['kept_event_id']}: "
                         f"Δt={x['time_delta_seconds']} s; Δvị trí={x['crossing_distance']}.")
        if not result['suppressed_candidates']:
            lines.append('- Không có event đạt đủ điều kiện của guard mới.')
        lines += ['',result['disclaimer'],'',
                  'Các quyết định loại trùng không dùng Ground Truth; GT chỉ dùng tính điểm sau giả lập.']
        (dest/'counterfactual.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
        print(f"Session #{result['session_id']}: AI {b['ai_total']} -> {a['ai_total']}, "
              f"missed {b['missed']} -> {a['missed']}, extra {b['false_positives']} -> {a['false_positives']}")
        print('Offline only; no database writes and no GPU replay.')
        return 0
    except (InvalidBenchmark, ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        print('[ERROR] Benchmark counterfactual failed:',str(exc),file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
