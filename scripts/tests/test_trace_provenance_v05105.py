"""V0.5.105: fail-closed stale session and declared schema validation."""
import contextlib
import gzip
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUDIT = load(ROOT / 'scripts/audit-gate-coverage.py', 'v105_gate_audit')
IDENTITY = load(ROOT / 'ai-service/app/trace_identity.py', 'v105_identity')


def mock_archive(path, meta, track=None):
    stream = [
        {'kind':'session_metadata','session_id':203,'camera_id':1,'source_fps':25,'source_frame_count':1,**meta},
        {'kind':'geometry_metadata','line':[[.1,.5],[.9,.5]],'frame_width':100,'frame_height':100},
        {'frame_index':1,'source_time_seconds':0.0,'gate_tracks':[track] if track else [],'road_tracks':1},
    ]
    with ZipFile(path,'w') as z:
        z.writestr('report.json',json.dumps({'missed_items':[],'false_positive_items':[]}))
        z.writestr('benchmark-trace.jsonl.gz',gzip.compress(('\n'.join(json.dumps(v) for v in stream)+'\n').encode()))


class TraceIdentityTests(unittest.TestCase):
    def setUp(self):
        self.integrity={'session_id':203,'benchmark_id':76,'ground_truth_total':0,'ai_total':0,
                        'matched':0,'missed':0,'extra':0,'source_trace_sha256':'0'*64}

    def test_source_hash_is_stable_and_sha256(self):
        first = IDENTITY.metadata()
        self.assertEqual(first, IDENTITY.metadata())
        self.assertEqual(first['ai_runtime_version'],(ROOT/'VERSION').read_text(encoding='utf-8').strip())
        self.assertRegex(first['worker_source_sha256'],r'^[a-f0-9]{64}$')
        self.assertEqual(first['gate_decision_scope'],'per-gate-track-v1')

    def test_expected_session_stops_before_opening_or_writing(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(AUDIT,'_verify',return_value=self.integrity):
            path=Path(tmp)/'old.zip'
            with self.assertRaisesRegex(ValueError,'expected Session #202'):
                AUDIT.build_report(path,expected_session=202)
            self.assertFalse(path.exists())

    def test_legacy_trace_is_reported_and_not_falsely_versioned(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(AUDIT,'_verify',return_value=self.integrity):
            path=Path(tmp)/'old.zip';mock_archive(path,{})
            value=AUDIT.build_report(path)
            self.assertEqual(value['runtime_provenance']['status'],'legacy-unattested')
            with self.assertRaisesRegex(ValueError,'legacy export'):
                AUDIT.build_report(path,require_provenance=True)

    def test_declared_schema_requires_all_track_decisions(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(AUDIT,'_verify',return_value=self.integrity):
            path=Path(tmp)/'bad.zip';mock_archive(path,IDENTITY.metadata(),
              {'track_id':5,'anchor':[50,51],'label':'motorcycle'})
            with self.assertRaisesRegex(ValueError,'schema missing track evidence'):
                AUDIT.build_report(path,require_provenance=True)

    def test_complete_schema_is_attested_without_changing_counts(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(AUDIT,'_verify',return_value=self.integrity):
            path=Path(tmp)/'good.zip';mock_archive(path,IDENTITY.metadata(),
              {'track_id':5,'anchor':[50,51],'label':'motorcycle',
               'primary_gate_decision':'pending-human-guard','final_gate_decision':'pending-human-guard'})
            value=AUDIT.build_report(path,expected_session=203,require_provenance=True)
            self.assertEqual(value['runtime_provenance']['status'],'verified-schema')
            self.assertEqual(value['runtime_provenance']['evidence_track_observations'],1)
            self.assertEqual(value['ai_total'],0)
            self.assertEqual(value['cases'],[])

    def test_declared_inconsistent_hash_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(AUDIT,'_verify',return_value=self.integrity):
            path=Path(tmp)/'bad.zip';meta=IDENTITY.metadata();meta['worker_source_sha256']='BAD'
            mock_archive(path,meta)
            with self.assertRaisesRegex(ValueError,'Inconsistent declared runtime provenance'):
                AUDIT.build_report(path)

    def test_older_declared_version_is_not_attested(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(AUDIT,'_verify',return_value=self.integrity):
            path=Path(tmp)/'oldversion.zip';meta=IDENTITY.metadata();meta['ai_runtime_version']='0.5.104'
            mock_archive(path,meta)
            with self.assertRaisesRegex(ValueError,'Inconsistent declared runtime provenance'):
                AUDIT.build_report(path)

    def test_read_only_gate_trace_has_explicit_pending_marker(self):
        content=(ROOT/'ai-service/app/worker.py').read_text()
        self.assertIn('"primary_gate_decision": "pending-human-guard"',content)
        self.assertIn('"final_gate_decision": "pending-human-guard"',content)
        self.assertIn('**trace_runtime_metadata()',content)
        main=(ROOT/'ai-service/app/main.py').read_text()
        self.assertIn('TRACE_RUNTIME_VERSION != APP_VERSION',main)


if __name__=='__main__':
    unittest.main()
