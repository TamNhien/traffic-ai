#!/usr/bin/env python3
"""V0.5.87: compare two independently verified GT benchmark ZIP exports.

This is *not* an inference runner or an accuracy optimizer. It neither modifies
Ground Truth nor infers vehicle identity from timestamp proximity. All metrics
are the backend's original one-to-one temporal assignment results.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
from zipfile import ZipFile

MAX_TRACE_ARCHIVE_BYTES = 128 * 1024 * 1024
ROOT = Path(__file__).resolve().parent


class ComparisonError(ValueError):
    pass


def _gate():
    spec = importlib.util.spec_from_file_location('traffic_benchmark_export_gate_v0587', ROOT / 'benchmark-gate.py')
    if spec is None or spec.loader is None:
        raise ComparisonError('Missing benchmark integrity gate')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _trace_integrity(path: Path, manifest: dict) -> str:
    trace = manifest.get('trace') or {}
    if not trace.get('available') or not trace.get('closed'):
        raise ComparisonError(f'{path.name}: trace is unavailable or not closed')
    names = ('benchmark-trace.jsonl.gz', 'benchmark-trace.jsonl')
    with ZipFile(path) as archive:
        included = [name for name in names if name in archive.namelist()]
        if len(included) != 1:
            raise ComparisonError(f'{path.name}: expected exactly one closed trace')
        name = included[0]
        info = archive.getinfo(name)
        file_info = (manifest.get('files') or {}).get(name) or {}
        if not 0 < info.file_size <= MAX_TRACE_ARCHIVE_BYTES or info.file_size != file_info.get('bytes'):
            raise ComparisonError(f'{path.name}: trace length mismatch/unsafe')
        digest = sha256()
        with archive.open(name) as reader:
            for block in iter(lambda: reader.read(1024 * 1024), b''):
                digest.update(block)
        if digest.hexdigest() != file_info.get('sha256') or digest.hexdigest() != trace.get('compressed_sha256'):
            raise ComparisonError(f'{path.name}: trace digest mismatch')
        return digest.hexdigest()


def _read_evidence(path: Path) -> dict:
    gate = _gate()
    try:
        report, manifest = gate.load_evidence(path)
        _trace_integrity(path, manifest)
        with ZipFile(path) as archive:
            events = json.loads(archive.read('events.json'))
            marks = json.loads(archive.read('ground-truth.json'))
            session = json.loads(archive.read('session.json'))
            config = json.loads(archive.read('config.json'))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ComparisonError(f'{path.name}: invalid benchmark evidence: {exc}') from exc
    if len(events) != report['ai_total'] or len(marks) != report['ground_truth_total']:
        raise ComparisonError(f'{path.name}: report count does not match the recorded rows')
    if session.get('id') != report.get('session_id') or manifest.get('session_id') != report.get('session_id'):
        raise ComparisonError(f'{path.name}: conflicting session IDs')
    return {'report': report, 'manifest': manifest, 'events': events, 'marks': marks,
            'session': session, 'config': config}


def _identity(row: dict) -> tuple:
    # Identical normalized event evidence across sessions; never compare DB IDs,
    # unstable ByteTrack IDs or wall-clock receipt timestamps.
    numeric = ('source_time_seconds', 'crossing_x', 'crossing_y', 'confidence')
    return (
        *tuple(round(float(row[k]), 6) if row.get(k) is not None else None for k in numeric),
        row.get('source_frame_index'),
        str(row.get('direction', '')).lower(), str(row.get('vehicle_type', '')).lower(),
        str(row.get('crossing_method', '')).lower(),
    )


def _metric(r: dict) -> dict:
    return {key: r.get(key) for key in (
        'ground_truth_total', 'ai_total', 'matched', 'missed', 'false_positives',
        'class_mismatches', 'direction_mismatches', 'counting_precision',
        'counting_recall', 'counting_f1', 'strict_matches', 'strict_f1',
    )}


def _case_signature(row: dict, kind: str) -> tuple:
    # Idempotent across cloned benchmark marks and copied sessions.
    if kind == 'missed':
        return (round(float(row['time']), 4), row.get('vehicle_type'), row.get('direction'))
    return (round(float(row['time']), 4), row.get('vehicle_type'), row.get('direction'), row.get('crossing_method'))


def _set_difference(left: Counter, right: Counter) -> list[list]:
    return [[*key, count] for key, count in sorted((left - right).items())]


def compare(prior: dict, current: dict) -> dict:
    p, c = prior['report'], current['report']
    if p['session_id'] == c['session_id']:
        raise ComparisonError('Same session cannot be treated as independent before/after comparison')
    if p['_verified_evidence']['source_fingerprint'] != c['_verified_evidence']['source_fingerprint']:
        raise ComparisonError('Clip/Gate/Road Zone geometry/FPS differs; comparison is invalid')
    if p['_verified_evidence']['gt_fingerprint'] != c['_verified_evidence']['gt_fingerprint']:
        raise ComparisonError('Ground Truth marks differ; repair/review GT before accuracy comparison')
    if p.get('tolerance_seconds') != c.get('tolerance_seconds'):
        raise ComparisonError('GT/AI time matching tolerance differs')
    if prior['session'].get('model_id') != current['session'].get('model_id'):
        # A different model may be a valid A/B experiment; disclose instead of rejecting.
        model_change = True
    else:
        model_change = False
    old_events = Counter(_identity(row) for row in prior['events'])
    new_events = Counter(_identity(row) for row in current['events'])
    old_missed = Counter(_case_signature(row, 'missed') for row in p['missed_items'])
    new_missed = Counter(_case_signature(row, 'missed') for row in c['missed_items'])
    old_extra = Counter(_case_signature(row, 'extra') for row in p['false_positive_items'])
    new_extra = Counter(_case_signature(row, 'extra') for row in c['false_positive_items'])
    before, after = _metric(p), _metric(c)
    metric_delta = {}
    for key in before:
        a, b = before[key], after[key]
        metric_delta[key] = round(b - a, 7) if type(a) in (float, int) and type(b) in (float, int) else None
    audit = c.get('temporal_assignment_audit', {})
    return {
        'format': 'traffic-ai-verified-benchmark-comparison', 'schema_version': 1,
        'prior': {'benchmark_id': p['benchmark']['id'], 'session_id': p['session_id'], 'metrics': before},
        'current': {'benchmark_id': c['benchmark']['id'], 'session_id': c['session_id'], 'metrics': after},
        'deltas': metric_delta,
        'same_ground_truth': True, 'same_source_geometry': True,
        'different_model': model_change,
        'same_recorded_ai_crossing_signatures': old_events == new_events,
        'ai_signatures_removed_count': sum((old_events - new_events).values()),
        'ai_signatures_added_count': sum((new_events - old_events).values()),
        'missed_cases_removed': _set_difference(old_missed, new_missed),
        'missed_cases_added': _set_difference(new_missed, old_missed),
        'extra_cases_removed': _set_difference(old_extra, new_extra),
        'extra_cases_added': _set_difference(new_extra, old_extra),
        'temporal_assignment_audit': {
            'identity_proven': bool(audit.get('identity_proven', False)),
            'missed_with_claimed_persisted_event': audit.get('missed_with_claimed_persisted_event'),
            'false_positives_near_assigned_ground_truth': audit.get('false_positives_near_assigned_ground_truth'),
        },
        'limitations': [
            'Timestamp-only GT assignment does not prove the same physical vehicle.',
            'Matching score deltas are not a GPU/model replay or a new prediction.',
            'Near-time AI events must not be suppressed or reclassified without visual identity evidence.',
        ],
    }


def to_markdown(info: dict) -> str:
    prev = info['prior']; curr = info['current']; diff = info['deltas']
    labels = [('GT', 'ground_truth_total'), ('AI đã lưu', 'ai_total'), ('Khớp timecode', 'matched'),
              ('Lọt', 'missed'), ('Dư', 'false_positives'), ('Sai loại', 'class_mismatches'),
              ('Sai hướng', 'direction_mismatches'), ('Precision', 'counting_precision'),
              ('Recall', 'counting_recall'), ('F1', 'counting_f1')]
    def format_value(key, val):
        return f'{val*100:.2f}%' if key.startswith('counting_') and type(val) in (int,float) else str(val)
    lines = [f'# Traffic AI — đối chiếu Benchmark #{prev["benchmark_id"]} / Session #{prev["session_id"]} → Benchmark #{curr["benchmark_id"]} / Session #{curr["session_id"]}',
             '', 'Đã xác minh SHA-256 các tệp JSON và trace, cùng nguồn video, hình học vạch đếm, thời gian ghép và GT.',
             '', '| Chỉ số | Trước | Sau | Chênh lệch |', '|---|---:|---:|---:|']
    for title,key in labels:
        lines.append(f'| {title} | {format_value(key,prev["metrics"][key])} | {format_value(key,curr["metrics"][key])} | {format_value(key,diff[key])} |')
    lines += ['', f'**Dấu vân tay sự kiện AI giống nhau:** {"CÓ" if info["same_recorded_ai_crossing_signatures"] else "KHÔNG"}.',
              f'**Chữ ký crossing mất đi / thêm vào:** {info["ai_signatures_removed_count"]} / {info["ai_signatures_added_count"]}.',
              f'**Mốc GT lọt được gỡ / xuất hiện:** {sum(x[-1] for x in info["missed_cases_removed"])} / {sum(x[-1] for x in info["missed_cases_added"])}.',
              f'**Sự kiện AI dư được gỡ / xuất hiện:** {sum(x[-1] for x in info["extra_cases_removed"])} / {sum(x[-1] for x in info["extra_cases_added"])}.', '']
    if all(diff.get(k) == 0 for k in ('matched','missed','false_positives')):
        lines += ['**Kết luận:** Chưa có cải thiện được đo lường trên bộ GT này.', '']
    elif diff['missed'] < 0 and diff['false_positives'] <= 0:
        lines += ['**Kết luận:** Kết quả ghép timecode cải thiện; cần xem lại các lượt xe cụ thể trước khi xác nhận cải thiện trên đối tượng vật lý.', '']
    else:
        lines += ['**Kết luận:** Có thay đổi trong kết quả ghép; cần đánh giá cân bằng lọt/dư trước khi phát hành.', '']
    audit = info['temporal_assignment_audit']
    lines += [f'- Lọt có sự kiện AI gần đó nhưng đã ghép với GT khác: **{audit["missed_with_claimed_persisted_event"]}**.',
              f'- Dư ở gần một GT đã có AI nhận: **{audit["false_positives_near_assigned_ground_truth"]}**.',
              '- Hai số trên không chứng minh danh tính xe, và không được tự động điều chỉnh GT.',
              '', '## Giới hạn', *('- '+msg for msg in info['limitations']), '']
    return '\n'.join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='Integrity-verified GT benchmark comparison (read-only)')
    ap.add_argument('--prior', required=True, type=Path, help='Previous benchmark ZIP')
    ap.add_argument('--current', required=True, type=Path, help='Current benchmark ZIP')
    ap.add_argument('--output-dir', type=Path, help='Optional directory to write JSON and Markdown')
    args = ap.parse_args(argv)
    try:
        info = compare(_read_evidence(args.prior), _read_evidence(args.current))
        print(to_markdown(info))
        if args.output_dir:
            args.output_dir.mkdir(parents=True,exist_ok=True)
            (args.output_dir/'benchmark-comparison.json').write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            (args.output_dir/'benchmark-comparison.md').write_text(to_markdown(info),encoding='utf-8')
            print(f'Báo cáo đã lưu: {args.output_dir.resolve()}')
        return 0
    except (ComparisonError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f'[ERROR] Không đủ bằng chứng đối chiếu: {exc}',file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
