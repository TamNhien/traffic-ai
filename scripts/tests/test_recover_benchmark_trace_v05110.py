"""V0.5.110 stdlib-only recovery regressions, no installed 7-Zip dependency."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile
from hashlib import sha256

FILE = Path(__file__).resolve().parents[1] / 'recover-benchmark-trace.py'
spec = importlib.util.spec_from_file_location('traffic_recover_05110', FILE)
recover_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recover_mod)


def fixture(folder, *, session=14, footer=True, frame_count=2, wrong_session=False):
    folder = Path(folder)
    trace = folder / 'camera-trace.jsonl'
    rows = [{'kind':'session_metadata', 'session_id':session+1 if wrong_session else session,
             'source_frame_count':frame_count, 'ai_runtime_version':'0.5.109'},
            {'kind':'geometry_metadata','session_id':session}]
    rows.extend({'camera_id':1,'session_id':session,'frame_index':i,
                 'source_time_seconds':i*0.04,'gate_tracks':[]} for i in range(1,frame_count+1))
    if footer:
        rows.append({'kind':'delivery_summary','session_id':session,'delivery_drain_complete':True,'pending_events':0})
    trace.write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf8')
    report={'benchmark':{'id':9},'session_id':session,'ground_truth_total':1,'ai_total':1,
            'matched':1,'missed':0,'false_positives':0}
    payload={'report.json':report,'ground-truth.json':[{'id':1}], 'events.json':[{'id':5}],
             'session.json':{'id':session}, 'config.json':{}}
    original={name:(json.dumps(value, sort_keys=True)+'\n').encode('utf8') for name,value in payload.items()}
    manifest={'format':'traffic-ai-benchmark-diagnostics','schema_version':1,'benchmark_id':9,
              'session_id':session,'trace':{'available':False,'reason':'too_large'},
              'files':{n:{'bytes':len(v),'sha256':sha256(v).hexdigest()} for n,v in original.items()},'notes':[]}
    inp=folder/'original.zip'
    with ZipFile(inp,'w') as z:
        for name,data in original.items():z.writestr(name,data)
        z.writestr('manifest.json',json.dumps(manifest)+'\n')
    return inp,trace,original


class RecoveryContract(unittest.TestCase):
    def test_preserves_original_evidence_and_frame_digest(self):
        with tempfile.TemporaryDirectory() as d:
            original,trace,payload=fixture(d)
            out=Path(d)/'recovered.zip'
            result=recover_mod.recover(original,out,trace_jsonl=trace)
            self.assertEqual(result['frame_count'],2)
            self.assertEqual(result['source_sha256'],sha256(trace.read_bytes()).hexdigest())
            with ZipFile(out) as z:
                self.assertIsNone(z.testzip())
                for name,data in payload.items():self.assertEqual(z.read(name),data)
                manifest=json.loads(z.read('manifest.json'))
                self.assertTrue(manifest['recovery']['derived_evidence'])
                self.assertTrue(manifest['trace']['closed'])
                self.assertIn('benchmark-trace.jsonl.gz',z.namelist())

    def test_refuses_wrong_session_without_output(self):
        with tempfile.TemporaryDirectory() as d:
            original,trace,_=fixture(d,wrong_session=True)
            out=Path(d)/'no.zip'
            with self.assertRaisesRegex(recover_mod.RecoveryError,'metadata'):
                recover_mod.recover(original,out,trace_jsonl=trace)
            self.assertFalse(out.exists())

    def test_refuses_incomplete_delivery_footer(self):
        with tempfile.TemporaryDirectory() as d:
            original,trace,_=fixture(d,footer=False)
            with self.assertRaisesRegex(recover_mod.RecoveryError,'closed'):
                recover_mod.recover(original,Path(d)/'no.zip',trace_jsonl=trace)

    def test_footer_must_be_last_record(self):
        with tempfile.TemporaryDirectory() as d:
            original,trace,_=fixture(d)
            with trace.open('a',encoding='utf8') as fp:
                fp.write(json.dumps({'kind':'unexpected_late_row'})+'\n')
            with self.assertRaisesRegex(recover_mod.RecoveryError,'closed'):
                recover_mod.recover(original,Path(d)/'no.zip',trace_jsonl=trace)

    def test_refuses_source_size_excess(self):
        with tempfile.TemporaryDirectory() as d:
            original,trace,_=fixture(d)
            with self.assertRaisesRegex(recover_mod.RecoveryError,'bounded'):
                recover_mod.recover(original,Path(d)/'no.zip',trace_jsonl=trace,max_source=20)

    def test_refuses_original_overwrite_or_existing_result(self):
        with tempfile.TemporaryDirectory() as d:
            original,trace,_=fixture(d)
            with self.assertRaisesRegex(recover_mod.RecoveryError,'new file'):
                recover_mod.recover(original,original,trace_jsonl=trace)
            out=Path(d)/'recovered.zip';out.touch()
            with self.assertRaisesRegex(recover_mod.RecoveryError,'new file'):
                recover_mod.recover(original,out,trace_jsonl=trace)

    def test_original_manifest_must_be_intact(self):
        with tempfile.TemporaryDirectory() as d:
            original,trace,_=fixture(d)
            with ZipFile(original,'a') as z:
                z.writestr('report.json',b'{}')
            with self.assertRaisesRegex(recover_mod.RecoveryError,'Duplicate|Invalid'):
                recover_mod.recover(original,Path(d)/'no.zip',trace_jsonl=trace)

    def test_exactly_one_source_required(self):
        with self.assertRaises(recover_mod.RecoveryError):
            with recover_mod.source_stream(camera_rar=None,trace_jsonl=None,session=1):pass


if __name__=='__main__':unittest.main()
