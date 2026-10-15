"""V0.5.92: verified same-canonical passage cycles never equate ID with vehicle."""
import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from test_compare_benchmark_exports_v0587 import make_benchmark

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('traffic_crossing_cycles_v0592', HERE / 'audit-crossing-cycles.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def event(eid, track, time, direction='in', method='direct', frame=None):
    return {'id':eid,'tracking_id':track,'source_time_seconds':time,'direction':direction,
            'crossing_method':method,'source_frame_index':frame if frame is not None else int(time*25+1)}


class CycleEvidenceTests(unittest.TestCase):
    def test_opposite_passage_same_id_is_only_a_review_candidate(self):
        events = [event(1,20,1,'in'),event(2,20,5,'out')]
        report = module.build_audit(events,[{'ai_event_id':2}])
        self.assertEqual(report['pairs_total'],1)
        self.assertTrue(report['pairs'][0]['current_extra'])
        self.assertFalse(report['pairs'][0]['identity_proven'])
        self.assertEqual(report['pairs'][0]['raw_provenance'],'insufficient_frame_witness')
        self.assertEqual([r['id'] for r in events],[1,2])

    def test_raw_alias_change_is_observation_not_identity_proof(self):
        result=module.build_audit([event(1,20,1),event(2,20,2,'out')],[],{
            26:{20:{'raw_track_id':100,'anchor_signed':-2.0,'stitched':False}},
            51:{20:{'raw_track_id':101,'anchor_signed':2.0,'stitched':True}},
        })
        self.assertEqual(result['raw_alias_changed_pairs'],1)
        self.assertEqual(result['pairs'][0]['raw_provenance'],'raw_alias_changed')
        self.assertFalse(result['pairs'][0]['identity_proven'])

    def test_unrelated_tracks_and_long_return_are_not_pairs(self):
        result=module.build_audit([event(1,1,1),event(2,2,1.1),event(3,1,22)],max_gap_seconds=12)
        self.assertEqual(result['pairs_total'],0)

    def test_rejected_nonfinite_and_duplicate_event_ids(self):
        with self.assertRaises(ValueError):module.build_audit([event(1,10,float('nan'))])
        with self.assertRaises(ValueError):module.build_audit([event(1,10,1),event(1,10,2)])
        with self.assertRaises(ValueError):module.build_audit([],max_gap_seconds=40)

    def test_export_csv_json_md(self):
        result=module.build_audit([event(1,20,1),event(2,20,2,'out')])
        with tempfile.TemporaryDirectory() as folder:
            module.write_audit(result,Path(folder))
            with (Path(folder)/'crossing-cycles.csv').open(encoding='utf-8-sig') as handle:
                self.assertEqual(len(list(csv.DictReader(handle))),1)
            self.assertIn('không chứng minh cùng xe',(Path(folder)/'crossing-cycles.md').read_text(encoding='utf8'))
            self.assertEqual(json.loads((Path(folder)/'crossing-cycles.json').read_text())['pairs_total'],1)

    def test_end_to_end_verified_archive_without_crossing_pair(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / 'verified.zip'
            make_benchmark(archive, 12)
            data = module.audit_archive(archive)
            self.assertEqual(data['events_total'], 1)
            self.assertEqual(data['pairs_total'], 0)
            self.assertEqual(data['benchmark_id'], 12)

    def test_corrupted_archive_is_rejected_before_provenance_analysis(self):
        import zipfile
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / 'corrupt.zip'
            make_benchmark(archive, 12)
            with zipfile.ZipFile(archive) as z:
                blobs = {name:z.read(name) for name in z.namelist()}
            blobs['benchmark-trace.jsonl'] = b'{"kind":"tampered"}\n'
            with zipfile.ZipFile(archive, 'w') as z:
                for name,body in blobs.items():z.writestr(name,body)
            with self.assertRaisesRegex(ValueError,'trace (?:length|digest)'):
                module.audit_archive(archive)

    def test_trace_witness_prefers_nearest_frame_and_zero_is_not_missing(self):
        w={100:{4:{'raw_track_id':0,'anchor_signed':0.0,'stitched':False}},
           102:{4:{'raw_track_id':5,'anchor_signed':0.1,'stitched':True}}}
        self.assertEqual(module._witness(w,101,4)['raw_track_id'],0)
        self.assertIsNone(module._witness(w,101,5)['frame'])

if __name__=='__main__':unittest.main()
