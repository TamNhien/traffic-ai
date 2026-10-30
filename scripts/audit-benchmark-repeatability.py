#!/usr/bin/env python3
"""V0.5.127: compare two verified GT runs and triage persistent defects, read-only.

A matching issue signature is not evidence of the same physical vehicle. This
utility never changes GT, events, AI policies, or production counters.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import gzip
import importlib.util
import io
import json
import math
from pathlib import Path
import sys
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent
MAX_CASES = 10000
MAX_POLICY_LINE = 128 * 1024


def _module(filename: str, alias: str):
    spec = importlib.util.spec_from_file_location(alias, ROOT / filename)
    if spec is None or spec.loader is None:
        raise ValueError(f'Cannot load verified auditor: {filename}')
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def _time(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError('Invalid issue source-time; cannot claim repeatability')
    return round(float(value), 3)


def _signature(kind: str, entry: dict) -> tuple:
    """Session-independent *review* signature; never compare DB or tracker IDs."""
    t = _time(entry['time'])
    if kind == 'missed':
        return (kind, t, entry.get('vehicle_type'), entry.get('direction'))
    if kind == 'extra':
        return (kind, t, entry.get('vehicle_type'), entry.get('direction'), entry.get('crossing_method'))
    if kind == 'direction':
        return (kind, t, entry.get('ground_truth_vehicle_type'),
                entry.get('ground_truth_direction'), entry.get('ai_direction'), entry.get('crossing_method'))
    if kind == 'class':
        return (kind, t, entry.get('ground_truth_vehicle_type'), entry.get('ai_vehicle_type'), entry.get('direction'))
    raise ValueError('Unsupported issue category')


PARTS = (('missed', 'missed_items', 'missed'), ('extra', 'false_positive_items', 'false_positives'),
         ('direction', 'direction_mismatch_items', 'direction_mismatches'),
         ('class', 'class_mismatch_items', 'class_mismatches'))


def _signatures(report: dict) -> Counter:
    results: Counter = Counter()
    for kind, list_name, count_name in PARTS:
        rows = report.get(list_name)
        if not isinstance(rows, list) or type(report.get(count_name)) is not int or len(rows) != report[count_name]:
            raise ValueError(f'Issue count mismatch for {list_name}')
        if len(rows) > MAX_CASES:
            raise ValueError('Too many review cases')
        for entry in rows:
            if not isinstance(entry, dict):
                raise ValueError('Invalid issue entry')
            results[_signature(kind, entry)] += 1
    if sum(results.values()) > MAX_CASES:
        raise ValueError('Too many issues')
    return results


def _policy_digest(export: Path, manifest: dict) -> tuple[str | None, str]:
    """Read certified prefix after full ZIP hash verification by compare module."""
    trace = manifest.get('trace') or {}
    if trace.get('available') is not True or trace.get('closed') is not True:
        raise ValueError('Certified closed trace required')
    with ZipFile(export) as zf:
        if 'benchmark-trace.jsonl.gz' not in zf.namelist():
            return None, 'unsupported_trace_encoding'
        with zf.open('benchmark-trace.jsonl.gz') as raw, gzip.GzipFile(fileobj=raw) as stream:
            for _ in range(8):
                line = stream.readline(MAX_POLICY_LINE + 1)
                if not line:
                    break
                if len(line) > MAX_POLICY_LINE:
                    raise ValueError('Unsafe trace policy prefix')
                obj = json.loads(line)
                if obj.get('kind') == 'policy_metadata':
                    digest = obj.get('configuration_sha256')
                    status = obj.get('capture_status')
                    if (status != 'complete' or not isinstance(digest, str) or len(digest) != 64
                            or any(c not in '0123456789abcdef' for c in digest)):
                        return None, 'policy_incomplete'
                    return digest, 'complete'
    return None, 'policy_not_recorded'


def summarize(previous: dict, current: dict, comparison: dict,
              previous_policy: tuple[str | None, str], current_policy: tuple[str | None, str]) -> dict:
    if not comparison.get('scoring_comparable') or not comparison.get('same_ground_truth') or not comparison.get('same_source_geometry'):
        raise ValueError('Comparable GT, geometry and source evidence required')
    old = _signatures(previous)
    now = _signatures(current)
    old_remaining = old.copy()
    rows = []
    audit = _module('audit-benchmark-quality.py', 'quality_v127')
    for kind, list_name, _ in PARTS:
        for entry in current[list_name]:
            sig = _signature(kind, entry)
            repeated = old_remaining[sig] > 0
            if repeated:
                old_remaining[sig] -= 1
            case = audit._issue(kind, entry)
            case['recurrence'] = 'repeated_signature' if repeated else 'new_signature'
            case['identity_proven'] = False
            case['priority'] = 'review_first' if kind in ('missed','extra') else 'review_class_direction'
            rows.append(case)
    rows.sort(key=lambda x: (x['time'], x['kind'], x.get('ai_event_id') or 0))
    for index, row in enumerate(rows, 1):
        row['review_id'] = f'REVIEW-{index:02d}'
    repeated_count = sum(x['recurrence'] == 'repeated_signature' for x in rows)
    resolved_count = sum(old_remaining.values())
    a, a_status = previous_policy
    b, b_status = current_policy
    same_policy = a == b if a and b else None
    same_events = comparison.get('same_recorded_ai_crossing_signatures') is True
    return {
        'format': 'traffic-ai-benchmark-repeatability', 'schema_version': 1,
        'prior': {'benchmark_id': comparison['prior']['benchmark_id'], 'session_id': comparison['prior']['session_id']},
        'current': {'benchmark_id': comparison['current']['benchmark_id'], 'session_id': comparison['current']['session_id']},
        'metrics_before': comparison['prior']['metrics'], 'metrics_after': comparison['current']['metrics'],
        'metrics_delta': comparison['deltas'],
        'sha256_verified': True, 'same_ground_truth': True, 'same_source_geometry': True,
        'same_ai_crossing_signatures': same_events,
        'ai_signatures_removed': comparison['ai_signatures_removed_count'],
        'ai_signatures_added': comparison['ai_signatures_added_count'],
        'recorded_policy': {'prior_status': a_status, 'current_status': b_status,
                            'prior_sha256': a, 'current_sha256': b, 'same_effective_policy': same_policy},
        'issue_totals': {'prior': sum(old.values()), 'current': len(rows),
                         'repeated_signatures': repeated_count, 'new_signatures': len(rows)-repeated_count,
                         'resolved_signatures': resolved_count},
        'no_measured_improvement': (same_events and
             all(comparison['deltas'].get(k) == 0 for k in
                 ('matched', 'missed', 'false_positives','class_mismatches','direction_mismatches'))),
        'read_only': True, 'accuracy_improvement_claimed': False,
        'limitations': [
            'A repeated issue signature is NOT proof of a repeated physical vehicle.',
            'A stable effective policy digest and identical events do NOT demonstrate that the detector is correct.',
            'The matching benchmark uses timecode assignment; review source MP4 and GT labels before changing AI policies.',
            'This report never modifies GT, persisted events, or model weights.'
        ], 'issues': rows,
    }


def analyze(prior: Path, current: Path) -> dict:
    compare = _module('compare-benchmark-exports.py', 'compare_v127')
    prev_data = compare._read_evidence(prior)
    curr_data = compare._read_evidence(current)
    result = compare.compare(prev_data, curr_data)
    if not result['scoring_comparable']:
        raise ValueError('Both benchmark ZIPs must contain scored GT')
    # Inspect policy *only after* independently verifying the transport SHA-256.
    prev_policy = _policy_digest(prior, prev_data['manifest'])
    curr_policy = _policy_digest(current, curr_data['manifest'])
    return summarize(prev_data['report'], curr_data['report'], result, prev_policy, curr_policy)


def _markdown(report: dict) -> str:
    a, b = report['prior'], report['current']
    n = report['issue_totals']
    p = report['recorded_policy']
    def tag(value):
        return 'CÓ' if value is True else ('KHÔNG' if value is False else 'CHƯA CÓ BẰNG CHỨNG')
    lines = [f'# Traffic AI — kiểm toán tái diễn #{a["benchmark_id"]} → #{b["benchmark_id"]}',
             '', 'Hai benchmark đã được kiểm tra SHA-256 và xác thực cùng nguồn video, GT và hình học vạch.',
             '', f'- Chữ ký crossing AI giống nhau: **{tag(report["same_ai_crossing_signatures"])}**.',
             f'- Policy hiệu lực cùng SHA-256: **{tag(p["same_effective_policy"])}**.',
             f'- Tình trạng policy: {p["prior_status"]} → {p["current_status"]}.',
             f'- Hồ sơ lỗi: trước **{n["prior"]}**, sau **{n["current"]}**, '
             f'lặp chữ ký **{n["repeated_signatures"]}**, mới **{n["new_signatures"]}**, '
             f'hết xuất hiện **{n["resolved_signatures"]}**.',
             '', f'**Không có cải thiện đo lường:** {tag(report["no_measured_improvement"])}.',
             '', '| Mốc video | Loại | Trạng thái | Gợi ý rà soát |', '|---|---|---|---|']
    for item in report['issues']:
        note = item['review_action'].replace('|','/')
        lines.append(f'| {item["timecode"]} | {item["kind"]} | {item["recurrence"]} | {note} |')
    lines.extend(['', '## Giới hạn', *('- '+x for x in report['limitations']), ''])
    return '\n'.join(lines)


def write_outputs(result: dict, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out/'repeatability.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n',encoding='utf-8')
    (out/'repeatability.md').write_text(_markdown(result),encoding='utf-8')
    fields = ('review_id', 'timecode', 'kind', 'recurrence','priority','ground_truth_id','ai_event_id',
              'ground_truth_class','ai_class','ground_truth_direction','ai_direction','crossing_method','audit_reason','review_action')
    with (out/'repeatability.csv').open('w', newline='', encoding='utf-8-sig') as fp:
        writer=csv.DictWriter(fp, fieldnames=fields, extrasaction='ignore'); writer.writeheader();writer.writerows(result['issues'])


def main(argv=None) -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--prior', type=Path, required=True)
    ap.add_argument('--current', type=Path, required=True)
    ap.add_argument('--output-dir', type=Path, default=Path('benchmark-repeatability-audit'))
    args=ap.parse_args(argv)
    try:
        result=analyze(args.prior,args.current)
        write_outputs(result,args.output_dir)
    except (ValueError, OSError, EOFError, RuntimeError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f'[FAIL] Benchmark repeatability audit (read-only): {exc}',file=sys.stderr)
        return 2
    print(f'[OK] Benchmark #{result["prior"]["benchmark_id"]} → #{result["current"]["benchmark_id"]}: '
          f'{result["issue_totals"]["repeated_signatures"]} repeated signatures; '
          f'{result["issue_totals"]["new_signatures"]} new / {result["issue_totals"]["resolved_signatures"]} resolved.')
    print(f'[OK] Same AI crossings: {result["same_ai_crossing_signatures"]}; '
          f'same recorded policy: {result["recorded_policy"]["same_effective_policy"]}; '
          f'no measured improvement: {result["no_measured_improvement"]}.')
    print(f'[OK] SHA-256 verified; reports: {args.output_dir}')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
