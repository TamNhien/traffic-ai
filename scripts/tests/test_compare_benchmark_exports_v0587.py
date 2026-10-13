"""V0.5.87 read-only two-benchmark integrity and stability regression."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'compare-benchmark-exports.py'
spec = importlib.util.spec_from_file_location('traffic_compare_benchmarks_v0587', SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def make_benchmark(path, session_id, *, gt_time=1.0, ai_time=1.0, method='direct', model=47):
    gt = {'id': 100 + session_id,'benchmark_id':session_id,'source_time_seconds':gt_time,'vehicle_type':'motorcycle','direction':'in'}
    ai = {'id': 400 + session_id,'session_id':session_id,'tracking_id':900 + session_id,
          'source_time_seconds':ai_time,'source_frame_index':int(ai_time*25),
          'crossing_x':.55,'crossing_y':.42,'confidence':.9,'direction':'in',
          'vehicle_type':'motorcycle','crossing_method':method}
    matched=abs(gt_time-ai_time)<=.75
    report={'session_id':session_id,'benchmark':{'id':session_id,'source_url':'clip1.mp4','source_fps':25.0,
            'source_duration_seconds':60.0,'geometry':{'line_x1':.4,'line_y1':.5}},
            'ground_truth_total':1,'ai_total':1,'matched':int(matched),'missed':int(not matched),
            'false_positives':int(not matched),'missed_items':[] if matched else [{'time':gt_time,'vehicle_type':'motorcycle','direction':'in'}],
            'false_positive_items':[] if matched else [{'time':ai_time,'vehicle_type':'motorcycle','direction':'in','crossing_method':method}],
            'matched_items':[{'time':gt_time}] if matched else [],'class_mismatches':0,'direction_mismatches':0,
            'counting_precision':float(matched),'counting_recall':float(matched),'counting_f1':float(matched),
            'strict_matches':int(matched),'strict_f1':float(matched),'tolerance_seconds':.75,
            'report_readiness':{'scoring_available':True},'integrity':{'ok':True},
            'temporal_assignment_audit':{'identity_proven':False,'missed_with_claimed_persisted_event':0,'false_positives_near_assigned_ground_truth':0}}
    trace=b'{"kind":"session_metadata"}\n'
    members={'report.json':report,'ground-truth.json':[gt],'events.json':[ai],
             'session.json':{'id':session_id,'model_id':model}, 'config.json':{}}
    blobs={k:json.dumps(v,sort_keys=True).encode('utf-8') for k,v in members.items()}
    blobs['benchmark-trace.jsonl']=trace
    files={name:{'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()} for name,body in blobs.items()}
    manifest={'format':'traffic-ai-benchmark-diagnostics','schema_version':1,
              'session_id':session_id,'files':files,
              'trace':{'available':True,'closed':True,'compressed_sha256':hashlib.sha256(trace).hexdigest()}}
    blobs['manifest.json']=json.dumps(manifest).encode('utf-8')
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for k,v in blobs.items():archive.writestr(k,v)


class BenchmarkComparisonTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Path(self.tmp.name)/'previous.zip';self.b=Path(self.tmp.name)/'current.zip'

    def compare(self):
        return module.compare(module._read_evidence(self.a), module._read_evidence(self.b))

    def test_same_crossings_ignore_run_id_and_tracker_ids(self):
        make_benchmark(self.a,1);make_benchmark(self.b,2)
        result=self.compare()
        self.assertTrue(result['same_recorded_ai_crossing_signatures'])
        self.assertEqual((result['ai_signatures_removed_count'],result['ai_signatures_added_count']),(0,0))
        self.assertEqual(result['deltas']['counting_f1'],0)
        self.assertIn('Chưa có cải thiện',module.to_markdown(result))

    def test_changed_event_method_is_reported_even_if_counts_stay_identical(self):
        make_benchmark(self.a,1);make_benchmark(self.b,2,method='rescued')
        result=self.compare()
        self.assertFalse(result['same_recorded_ai_crossing_signatures'])
        self.assertEqual((result['ai_signatures_removed_count'],result['ai_signatures_added_count']),(1,1))

    def test_incompatible_gt_is_rejected(self):
        make_benchmark(self.a,1);make_benchmark(self.b,2,gt_time=2.0)
        with self.assertRaisesRegex(module.ComparisonError,'Ground Truth'):
            self.compare()

    def test_different_session_required(self):
        make_benchmark(self.a,1);make_benchmark(self.b,1)
        with self.assertRaisesRegex(module.ComparisonError,'Same session'):
            self.compare()

    def test_archive_payload_tampering_rejected(self):
        make_benchmark(self.a,1);make_benchmark(self.b,2)
        with zipfile.ZipFile(self.b) as archive:
            blobs={x.filename:archive.read(x.filename) for x in archive.infolist()}
        blobs['benchmark-trace.jsonl']=b'{"kind":"tampered"}\n'
        with zipfile.ZipFile(self.b,'w') as archive:
            for name,contents in blobs.items():archive.writestr(name,contents)
        with self.assertRaisesRegex(module.ComparisonError,'trace (?:digest|length)'):
            module._read_evidence(self.b)

    def test_model_change_disclosed_without_inventing_a_failure(self):
        make_benchmark(self.a,1,model=47);make_benchmark(self.b,2,model=48)
        self.assertTrue(self.compare()['different_model'])

    def test_count_evidence_must_match_export_rows(self):
        make_benchmark(self.a,1)
        with zipfile.ZipFile(self.a) as archive:blobs={x.filename:archive.read(x.filename) for x in archive.infolist()}
        original=json.loads(blobs['report.json']);original['ai_total']=2
        blobs['report.json']=json.dumps(original).encode('utf8')
        manifest=json.loads(blobs['manifest.json'])
        manifest['files']['report.json']={'bytes':len(blobs['report.json']),'sha256':hashlib.sha256(blobs['report.json']).hexdigest()}
        blobs['manifest.json']=json.dumps(manifest).encode('utf8')
        with zipfile.ZipFile(self.a,'w') as archive:
            for k,v in blobs.items():archive.writestr(k,v)
        with self.assertRaises(module.ComparisonError):module._read_evidence(self.a)


if __name__=='__main__':unittest.main()
