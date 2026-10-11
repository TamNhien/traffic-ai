"""Contract tests: measured mismatches cannot be disguised by equal totals."""
from __future__ import annotations

import importlib.util
import json
import hashlib
import zipfile
from pathlib import Path

import pytest

GATE = Path(__file__).resolve().parents[1] / 'benchmark-gate.py'
spec = importlib.util.spec_from_file_location('traffic_ai_benchmark_gate', GATE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def _make_export(path, gt_count, ai_count, match_count, *, integrity=True, marks=True):
    missed = gt_count - match_count
    extras = ai_count - match_count
    report = {
        'benchmark': {'id': 51}, 'session_id': 174,
        'report_readiness': {'scoring_available': marks},
        'ground_truth_total': gt_count, 'ai_total': ai_count, 'matched': match_count,
        'missed': missed, 'false_positives': extras, 'class_mismatches': 2,
        'matched_items': [{} for _ in range(match_count)],
        'missed_items': [{} for _ in range(missed)],
        'false_positive_items': [{} for _ in range(extras)],
        'tolerance_seconds': .75, 'integrity': {'ok': integrity},
    }
    records = {
        'report.json': report, 'ground-truth.json': [
            {'source_time_seconds': float(i), 'direction': 'in', 'vehicle_type': 'motorcycle'}
            for i in range(gt_count)],
        'events.json': [{}] * ai_count, 'session.json': {}, 'config.json': {},
    }
    blobs = {k: (json.dumps(v)+'\n').encode() for k, v in records.items()}
    manifest = {'format': 'traffic-ai-benchmark-diagnostics', 'schema_version': 1,
                'files': {k: {'sha256': hashlib.sha256(v).hexdigest(), 'bytes': len(v)}
                          for k,v in blobs.items()}}
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for name,data in blobs.items():z.writestr(name,data)
        z.writestr('manifest.json',json.dumps(manifest))


def test_v0572_equal_totals_do_not_mean_no_errors(tmp_path):
    export = tmp_path/'r.zip'
    _make_export(export,149,149,135)
    report, _ = module.load_evidence(export)
    assert report['ground_truth_total'] == report['ai_total'] == 149
    assert module.metrics(report)['matched'] == 135
    assert module.main(['--export',str(export)]) == 1
    assert module.main(['--export',str(export),'--max-missed','14','--max-extra','14']) == 0


def test_v0572_verified_perfect_benchmark_can_pass(tmp_path):
    export = tmp_path/'perfect.zip'
    _make_export(export,149,149,149)
    assert module.main(['--export',str(export)]) == 0
    assert module.main(['--export',str(export),'--max-class-mismatches','0']) == 1


def test_v0572_ground_truth_required(tmp_path):
    export = tmp_path/'not_ready.zip'
    _make_export(export,149,149,135,marks=False)
    assert module.main(['--export',str(export)]) == 2


def test_v0572_integrity_failure_blocks_release(tmp_path):
    export = tmp_path/'corrupt.zip'
    _make_export(export,149,149,149,integrity=False)
    assert module.main(['--export',str(export)]) == 2
    with zipfile.ZipFile(export,'a') as z:
        z.writestr('report.json','{}')
    assert module.main(['--export',str(export)]) == 2


def test_v0572_baseline_must_be_same_gt_and_tolerance():
    now={'ground_truth_total':149,'tolerance_seconds':.75,'matched':135,'missed':14,'false_positives':14,'class_mismatches':2}
    baseline=dict(now)
    assert module.evaluate(now,max_missed=14,max_extra=14,max_class_mismatches=None,baseline=baseline)==[]
    changed=dict(now,missed=15)
    assert any('regressed' in msg for msg in module.evaluate(changed,max_missed=20,max_extra=20,max_class_mismatches=None,baseline=baseline))
    baseline['tolerance_seconds']=1.0
    assert any('cannot compare' in msg for msg in module.evaluate(now,max_missed=20,max_extra=20,max_class_mismatches=None,baseline=baseline))
