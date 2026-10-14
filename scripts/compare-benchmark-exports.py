#!/usr/bin/env python3
"""V0.5.90: verify two benchmark exports, with a safe AI-only fallback for GT=0.

A scoring comparison requires two completed, identical GT sets.  Unscored ZIPs
can compare only persisted AI signatures; accuracy metrics are never inferred.
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
        with ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise ComparisonError(f'{path.name}: duplicate ZIP member name')
            if any(name not in names for name in gate.REQUIRED):
                raise ComparisonError(f'{path.name}: incomplete benchmark export')
            manifest, _ = gate._load_json(archive, 'manifest.json')
            if manifest.get('format') != 'traffic-ai-benchmark-diagnostics' or manifest.get('schema_version') != 1:
                raise ComparisonError(f'{path.name}: unsupported benchmark schema')
            data = {}
            for name in gate.REQUIRED[1:]:
                obj, raw = gate._load_json(archive, name)
                expected = (manifest.get('files') or {}).get(name) or {}
                if expected.get('sha256') != sha256(raw).hexdigest() or expected.get('bytes') != len(raw):
                    raise ComparisonError(f'{path.name}: evidence hash mismatch for {name}')
                data[name] = obj
            report = data['report.json']
            events = data['events.json']
            marks = data['ground-truth.json']
            session = data['session.json']
            config = data['config.json']
        _trace_integrity(path, manifest)
        if not (isinstance(report, dict) and isinstance(events, list) and isinstance(marks, list)
                and isinstance(session, dict) and isinstance(config, dict)):
            raise ComparisonError(f'{path.name}: invalid data shape')
        if not all(isinstance(event, dict) for event in events):
            raise ComparisonError(f'{path.name}: invalid crossing event row')
        if (type(report.get('ai_total')) is not int or report['ai_total'] < 0
                or len(events) != report['ai_total']):
            raise ComparisonError(f'{path.name}: report count does not match the recorded rows')
        if (session.get('id') != report.get('session_id')
                or manifest.get('session_id') != report.get('session_id')):
            raise ComparisonError(f'{path.name}: conflicting session IDs')
        if report.get('integrity', {}).get('ok') is not True:
            raise ComparisonError(f'{path.name}: backend/event persistence integrity failed')
        readiness = report.get('report_readiness') or {}
        scored = readiness.get('scoring_available') is True
        if scored:
            # Preserve the complete fail-closed GT conservation and integrity gate.
            report, _ = gate.load_evidence(path)
            if len(marks) != report['ground_truth_total']:
                raise ComparisonError(f'{path.name}: inconsistent GT rows')
        else:
            # An archive exported BEFORE a GT copy is still useful for comparing
            # AI events. It cannot substantiate any matching/missed/F1 claims.
            if (readiness.get('scoring_available') is not False
                    or report.get('ground_truth_total') != 0 or len(marks) != 0
                    or any(report.get(k) is not None for k in
                           ('matched', 'missed', 'false_positives', 'counting_f1'))):
                raise ComparisonError(f'{path.name}: ambiguous unscored benchmark state')
            source = report.get('benchmark') or {}
            source_identity = {
                'source': source.get('source_url'),
                'source_fps': source.get('source_fps'),
                'source_duration_seconds': source.get('source_duration_seconds'),
                'geometry': source.get('geometry'),
            }
            report['_verified_evidence'] = {
                'source_fingerprint': sha256(json.dumps(source_identity, sort_keys=True).encode('utf-8')).hexdigest(),
                'gt_fingerprint': None,
            }
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ComparisonError(f'{path.name}: invalid benchmark evidence: {exc}') from exc
    return {'report': report, 'manifest': manifest, 'events': events, 'marks': marks,
            'session': session, 'config': config, 'scored': scored}

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
    scored_pair = prior['scored'] and current['scored']
    if scored_pair:
        if p['_verified_evidence']['gt_fingerprint'] != c['_verified_evidence']['gt_fingerprint']:
            raise ComparisonError('Ground Truth marks differ; repair/review GT before accuracy comparison')
        if p.get('tolerance_seconds') != c.get('tolerance_seconds'):
            raise ComparisonError('GT/AI time matching tolerance differs')

    old_events = Counter(_identity(row) for row in prior['events'])
    new_events = Counter(_identity(row) for row in current['events'])
    before, after = _metric(p), _metric(c)
    # A missing GT in either archive MUST disable every accuracy delta, even if
    # the other archive has a completed score and the totals happen to match.
    metric_delta = {}
    for key in before:
        a, b = before[key], after[key]
        metric_delta[key] = (round(b - a, 7)
                             if scored_pair and type(a) in (float, int) and type(b) in (float, int)
                             else None)
    if scored_pair:
        old_missed = Counter(_case_signature(row, 'missed') for row in p['missed_items'])
        new_missed = Counter(_case_signature(row, 'missed') for row in c['missed_items'])
        old_extra = Counter(_case_signature(row, 'extra') for row in p['false_positive_items'])
        new_extra = Counter(_case_signature(row, 'extra') for row in c['false_positive_items'])
        missed_removed = _set_difference(old_missed, new_missed)
        missed_added = _set_difference(new_missed, old_missed)
        extra_removed = _set_difference(old_extra, new_extra)
        extra_added = _set_difference(new_extra, old_extra)
        audit = c.get('temporal_assignment_audit', {})
    else:
        missed_removed = missed_added = extra_removed = extra_added = None
        audit = {}
    return {
        'format': 'traffic-ai-verified-benchmark-comparison', 'schema_version': 2,
        'comparison_mode': 'scored' if scored_pair else 'ai_events_only',
        'scoring_comparable': bool(scored_pair),
        'prior': {'benchmark_id': p['benchmark']['id'], 'session_id': p['session_id'],
                  'scored': prior['scored'], 'metrics': before},
        'current': {'benchmark_id': c['benchmark']['id'], 'session_id': c['session_id'],
                    'scored': current['scored'], 'metrics': after},
        'deltas': metric_delta,
        'same_ground_truth': True if scored_pair else None,
        'same_source_geometry': True,
        'different_model': prior['session'].get('model_id') != current['session'].get('model_id'),
        'same_recorded_ai_crossing_signatures': old_events == new_events,
        'ai_signatures_removed_count': sum((old_events - new_events).values()),
        'ai_signatures_added_count': sum((new_events - old_events).values()),
        'missed_cases_removed': missed_removed, 'missed_cases_added': missed_added,
        'extra_cases_removed': extra_removed, 'extra_cases_added': extra_added,
        'temporal_assignment_audit': {
            'identity_proven': bool(audit.get('identity_proven', False)),
            'missed_with_claimed_persisted_event': audit.get('missed_with_claimed_persisted_event'),
            'false_positives_near_assigned_ground_truth': audit.get('false_positives_near_assigned_ground_truth'),
        },
        'limitations': [
            'Timestamp-only GT assignment does not prove the same physical vehicle.',
            'Matching score deltas are not a GPU/model replay or a new prediction.',
            'Near-time AI events must not be suppressed or reclassified without visual identity evidence.',
            *([] if scored_pair else [
                'At least one ZIP was exported before GT scoring; all missed/extra/precision/recall/F1 deltas are unavailable.',
                'To compare accuracy, copy/review GT then download a NEW benchmark export ZIP.',
            ]),
        ],
    }

def to_markdown(info: dict) -> str:
    prev = info['prior']; curr = info['current']; diff = info['deltas']
    title = (f'# Traffic AI — đối chiếu Benchmark #{prev["benchmark_id"]} / Session #{prev["session_id"]}'
             f' → Benchmark #{curr["benchmark_id"]} / Session #{curr["session_id"]}')
    if not info['scoring_comparable']:
        lines = [title, '', '**CHẾ ĐỘ CHỈ SO SÁNH SỰ KIỆN AI — KHÔNG CHẤM ĐIỂM.**',
                 '', 'Cả hai ZIP đã được kiểm tra hash JSON, trace, cùng video và hình học vạch đếm.',
                 '', '| Chỉ số | Trước | Sau |', '|---|---:|---:|',
                 f'| GT trong bản ZIP | {prev["metrics"]["ground_truth_total"]} | {curr["metrics"]["ground_truth_total"]} |',
                 f'| AI đã lưu | {prev["metrics"]["ai_total"]} | {curr["metrics"]["ai_total"]} |',
                 '| Lọt / dư / Precision / Recall / F1 | Không so sánh | Không so sánh |',
                 '', f'**Dấu vân tay crossing AI giống nhau:** {"CÓ" if info["same_recorded_ai_crossing_signatures"] else "KHÔNG"}.',
                 f'**Sự kiện AI mất / thêm:** {info["ai_signatures_removed_count"]} / {info["ai_signatures_added_count"]}.',
                 '', '**Cần tải lại ZIP sau khi sao chép GT** nếu giao diện hiện có 149 GT nhưng ZIP cũ vẫn là GT 0.',
                 '', '## Giới hạn', *('- '+msg for msg in info['limitations']), '']
        return '\n'.join(lines)

    labels = [('GT', 'ground_truth_total'), ('AI đã lưu', 'ai_total'), ('Khớp timecode', 'matched'),
              ('Lọt', 'missed'), ('Dư', 'false_positives'), ('Sai loại', 'class_mismatches'),
              ('Sai hướng', 'direction_mismatches'), ('Precision', 'counting_precision'),
              ('Recall', 'counting_recall'), ('F1', 'counting_f1')]
    def format_value(key, val):
        return f'{val*100:.2f}%' if key.startswith('counting_') and type(val) in (int,float) else str(val)
    lines = [title, '', 'Đã xác minh SHA-256 các tệp JSON và trace, cùng nguồn video, hình học vạch đếm, thời gian ghép và GT.',
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
