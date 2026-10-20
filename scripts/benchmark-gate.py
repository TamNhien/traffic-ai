#!/usr/bin/env python3
"""V0.5.72: fail-closed quality gate for an exported Traffic AI benchmark.

Use a full 'Tai ho so benchmark' export, not a screenshot or camera JPG RAR.
This does not alter GT marks or AI events and cannot change AI counts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

MAX_JSON_BYTES = 16 * 1024 * 1024
REQUIRED = ('manifest.json', 'report.json', 'ground-truth.json', 'events.json', 'session.json', 'config.json')


class BenchmarkEvidenceError(ValueError):
    pass


def _load_json(archive: zipfile.ZipFile, filename: str):
    info = archive.getinfo(filename)
    if info.file_size > MAX_JSON_BYTES or info.file_size <= 0:
        raise BenchmarkEvidenceError(f'{filename} is too large or empty')
    data = archive.read(filename)
    if len(data) != info.file_size:
        raise BenchmarkEvidenceError(f'{filename} was truncated')
    try:
        return json.loads(data), data
    except (ValueError, UnicodeError) as exc:
        raise BenchmarkEvidenceError(f'{filename} is not valid UTF-8 JSON') from exc


def load_evidence(filepath: str | Path) -> tuple[dict, dict]:
    # V0.5.111: distinguish a missing local download from an invalid ZIP.
    # This happens *before* trace/session validation and never alters evidence.
    source = Path(filepath).expanduser()
    display_path = str(source.resolve())
    if not source.is_file():
        if source.exists():
            raise BenchmarkEvidenceError(f'Benchmark ZIP path is not a file: {display_path}')
        raise BenchmarkEvidenceError(
            f'Benchmark ZIP not found: {display_path}. Download/copy the recovered ZIP '
            'to this path, or pass its full absolute path to -Export.'
        )
    try:
        with zipfile.ZipFile(source) as archive:
            if len(archive.namelist()) != len(set(archive.namelist())):
                raise BenchmarkEvidenceError('Duplicate ZIP member names are not allowed')
            if any(name not in archive.namelist() for name in REQUIRED):
                raise BenchmarkEvidenceError('Not a complete Traffic AI benchmark export ZIP')
            manifest, _ = _load_json(archive, 'manifest.json')
            if manifest.get('format') != 'traffic-ai-benchmark-diagnostics' or manifest.get('schema_version') != 1:
                raise BenchmarkEvidenceError('Unexpected benchmark export format/schema')
            data = {}
            for name in REQUIRED[1:]:
                obj, raw = _load_json(archive, name)
                record = manifest.get('files', {}).get(name)
                if (not isinstance(record, dict) or record.get('sha256') != hashlib.sha256(raw).hexdigest()
                        or record.get('bytes') != len(raw)):
                    raise BenchmarkEvidenceError(f'Integrity/manifest mismatch: {name}')
                data[name] = obj
    except zipfile.BadZipFile as exc:
        raise BenchmarkEvidenceError(
            f'Invalid/truncated benchmark ZIP: {display_path}. Re-download the recovered ZIP.'
        ) from exc
    except PermissionError as exc:
        raise BenchmarkEvidenceError(
            f'Access denied reading benchmark ZIP: {display_path}. Close applications locking the file.'
        ) from exc
    except KeyError as exc:
        raise BenchmarkEvidenceError(
            f'Benchmark ZIP is missing a required member: {exc}'
        ) from exc
    except OSError as exc:
        raise BenchmarkEvidenceError(
            f'I/O error reading benchmark ZIP: {display_path} ({exc.__class__.__name__}).'
        ) from exc
    report = data['report.json']
    if not isinstance(report, dict) or report.get('report_readiness', {}).get('scoring_available') is not True:
        raise BenchmarkEvidenceError('Benchmark has no completed Ground Truth; refusing to score')
    gt, ai = report.get('ground_truth_total'), report.get('ai_total')
    matched, missed, extra = report.get('matched'), report.get('missed'), report.get('false_positives')
    if any(type(x) is not int or x < 0 for x in (gt, ai, matched, missed, extra)):
        raise BenchmarkEvidenceError('Missing/invalid benchmark count fields')
    if matched + missed != gt or matched + extra != ai:
        raise BenchmarkEvidenceError('Impossible GT/AI/matched/missed/extra conservation')
    if len(data['ground-truth.json']) != gt:
        raise BenchmarkEvidenceError('Ground Truth mark list disagrees with the report')
    if len(report.get('missed_items', [])) != missed or len(report.get('false_positive_items', [])) != extra:
        raise BenchmarkEvidenceError('Unmatched lists disagree with benchmark totals')
    if len(report.get('matched_items', [])) != matched:
        raise BenchmarkEvidenceError('Matched list disagrees with benchmark totals')
    if len(data['events.json']) < ai:
        raise BenchmarkEvidenceError('Export event list is shorter than scored AI events')
    # A copied benchmark has new database IDs but the same physical GT marks.
    # Fingerprint only the scoring identity, not rows' mutable IDs/timestamps.
    gt_identity = sorted((
        round(float(row['source_time_seconds']), 6),
        str(row.get('direction', '')).lower(),
        str(row.get('vehicle_type', '')).lower(),
    ) for row in data['ground-truth.json'])
    source = report.get('benchmark') or {}
    source_identity = {
        'source': source.get('source_url'), 'source_fps': source.get('source_fps'),
        'source_duration_seconds': source.get('source_duration_seconds'),
        'geometry': source.get('geometry'),
    }
    report['_verified_evidence'] = {
        'gt_fingerprint': hashlib.sha256(json.dumps(gt_identity, sort_keys=True).encode('utf-8')).hexdigest(),
        'source_fingerprint': hashlib.sha256(json.dumps(source_identity, sort_keys=True).encode('utf-8')).hexdigest(),
    }
    if not isinstance(report.get('integrity'), dict) or report['integrity'].get('ok') is not True:
        raise BenchmarkEvidenceError('Backend/event persistence integrity did not pass')
    return report, manifest


def metrics(report: dict) -> dict:
    return {
        'benchmark_id': report.get('benchmark', {}).get('id'),
        'session_id': report.get('session_id'),
        'ground_truth_total': int(report['ground_truth_total']),
        'ai_total': int(report['ai_total']),
        'matched': int(report['matched']),
        'missed': int(report['missed']),
        'false_positives': int(report['false_positives']),
        'class_mismatches': int(report.get('class_mismatches', 0)),
        'tolerance_seconds': report.get('tolerance_seconds'),
        **report.get('_verified_evidence', {}),
    }


def evaluate(current: dict, *, max_missed: int, max_extra: int, max_class_mismatches: int | None, baseline: dict | None = None) -> list[str]:
    failures = []
    if current['missed'] > max_missed:
        failures.append(f"missed={current['missed']} > {max_missed}")
    if current['false_positives'] > max_extra:
        failures.append(f"extra={current['false_positives']} > {max_extra}")
    if max_class_mismatches is not None and current['class_mismatches'] > max_class_mismatches:
        failures.append(f"wrong_class={current['class_mismatches']} > {max_class_mismatches}")
    if baseline is not None:
        # Compare only equivalent GT, benchmark and tolerance; comparing a
        # different clip/GT set would create a misleading pass/failure.
        for key in ('ground_truth_total', 'tolerance_seconds', 'gt_fingerprint', 'source_fingerprint'):
            if current.get(key) != baseline.get(key):
                failures.append(f'baseline {key} differs; cannot compare')
        if not failures:
            for key in ('missed', 'false_positives', 'class_mismatches'):
                if current[key] > baseline[key]:
                    failures.append(f'{key} regressed from {baseline[key]} to {current[key]}')
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Traffic AI full-benchmark quality gate (fail closed)')
    parser.add_argument('--export', type=Path, required=True, help='ZIP file from Tai ho so benchmark')
    parser.add_argument('--max-missed', type=int, default=0)
    parser.add_argument('--max-extra', type=int, default=0)
    parser.add_argument('--max-class-mismatches', type=int, default=None)
    parser.add_argument('--baseline', type=Path, help='Earlier verified baseline JSON')
    parser.add_argument('--write-baseline', type=Path, help='Write measured baseline JSON (cannot fabricate zero errors)')
    args = parser.parse_args(argv)
    if min(args.max_missed, args.max_extra) < 0 or (args.max_class_mismatches is not None and args.max_class_mismatches < 0):
        parser.error('thresholds must be nonnegative')
    try:
        report, _ = load_evidence(args.export)
        current = metrics(report)
        prior = None
        if args.baseline is not None:
            prior = json.loads(args.baseline.read_text(encoding='utf-8'))
            if not isinstance(prior, dict):
                raise BenchmarkEvidenceError('Baseline must be a JSON object')
        failures = evaluate(current, max_missed=args.max_missed, max_extra=args.max_extra,
                            max_class_mismatches=args.max_class_mismatches, baseline=prior)
        print(f"Benchmark #{current['benchmark_id']} / Session #{current['session_id']}: "
              f"GT {current['ground_truth_total']} | AI {current['ai_total']} | "
              f"Matched {current['matched']} | Missed {current['missed']} | Extra {current['false_positives']} | "
              f"Wrong class {current['class_mismatches']}")
        if args.write_baseline is not None:
            args.write_baseline.parent.mkdir(parents=True, exist_ok=True)
            args.write_baseline.write_text(json.dumps(current, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            print(f'Wrote observed baseline: {args.write_baseline}')
        if failures:
            print('[FAIL] Benchmark release gate: ' + '; '.join(failures), file=sys.stderr)
            return 1
        print('[PASS] Benchmark release gate')
        return 0
    except (BenchmarkEvidenceError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f'[ERROR] Invalid benchmark evidence: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
