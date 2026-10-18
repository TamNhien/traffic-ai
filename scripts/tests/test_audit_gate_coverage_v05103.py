"""V0.5.103 gate-coverage evidence cannot authorize GT edits or automatic counts."""
import csv
import importlib.util
import json
import math
import tempfile
import unittest
from pathlib import Path


def get_api():
    path=Path(__file__).parents[1]/'audit-gate-coverage.py'
    spec=importlib.util.spec_from_file_location('traffic_gate_coverage_103',path)
    api=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
    return api


class GateCoverageTests(unittest.TestCase):
    def setUp(self):
        self.api=get_api()
        self.case={'kind':'missed','case_id':10822,'time_s':591.091,
                   'direction':'in','vehicle_type':'bicycle'}

    def point(self,frame,signed,owner=22,u=.5):
        return {'frame':frame,'time':(frame-1)/25,'track_id':owner,'raw_track_id':owner,
                'u':u,'signed':signed,'label':'motorcycle'}

    def test_normalized_gate_point(self):
        # A horizontal midline from x=0.2..0.8 at y=0.4.
        line=[[.2,.4],[.8,.4]]
        proj,signed=self.api.point_gate_geometry([500,400],line,1000,1000)
        self.assertAlmostEqual(proj,.5)
        self.assertAlmostEqual(signed,0)

    def test_degenerate_or_nonfinite_geometry_rejected(self):
        self.assertIsNone(self.api.point_gate_geometry([math.nan,10],[[0,0],[1,1]],100,100))
        self.assertIsNone(self.api.point_gate_geometry(None,[[0,0],[1,1]],100,100))
        with self.assertRaises(ValueError):
            self.api.point_gate_geometry([3,4],[[.5,.5],[.5,.5]],100,100)
        with self.assertRaises(ValueError):
            self.api.point_gate_geometry([3,4],[[0,0],[1,1]],0,100)

    def test_no_witness_cannot_be_called_detector_failure(self):
        row=self.api.case_witnesses(self.case,[])
        self.assertEqual(row['near_gate_tracks'],0)
        self.assertEqual(row['finite_segment_span_candidates'],0)
        self.assertFalse(row['auto_recount_permitted'])
        self.assertFalse(row['physical_identity_proven'])

    def test_verified_span_is_only_weak_geometry_candidate(self):
        row=self.api.case_witnesses(self.case,[self.point(100,-.007),self.point(102,.008)])
        self.assertEqual(row['near_gate_tracks'],1)
        self.assertEqual(row['finite_segment_span_candidates'],1)
        self.assertFalse(row['auto_recount_permitted'])
        self.assertEqual(row['nearest_tracks'][0]['track_id'],22)

    def test_two_distant_vehicles_do_not_automatically_merge(self):
        tracks=[self.point(100,-.01,owner=191795,u=.07),
                self.point(101,.01,owner=191795,u=.08),
                self.point(100,-.01,owner=192389,u=.82),
                self.point(101,.01,owner=192389,u=.83)]
        row=self.api.case_witnesses(self.case,tracks)
        self.assertEqual(row['near_gate_tracks'],2)
        self.assertEqual(len(row['nearest_tracks']),2)
        self.assertEqual(row['finite_segment_span_candidates'],2)
        self.assertFalse(row['physical_identity_proven'])

    def test_distant_from_segment_is_not_near_gate(self):
        values=[self.point(100,-.005,u=1.35),self.point(101,.005,u=1.37)]
        row=self.api.case_witnesses(self.case,values)
        self.assertEqual(row['near_gate_tracks'],0)

    def test_time_gap_does_not_fake_track_span(self):
        row=self.api.case_witnesses(self.case,[self.point(100,-.015),self.point(130,.015)])
        self.assertEqual(row['finite_segment_span_candidates'],0)

    def test_same_side_never_spans(self):
        row=self.api.case_witnesses(self.case,[self.point(100,-.01),self.point(102,-.005)])
        self.assertEqual(row['finite_segment_span_candidates'],0)

    def test_per_track_candidates_bounded_to_six(self):
        row=self.api.case_witnesses(self.case,[self.point(100,-.001,owner=i) for i in range(20)])
        self.assertEqual(len(row['nearest_tracks']),6)
        self.assertEqual(row['track_candidates_truncated'],14)

    def test_invalid_radius_fails_closed(self):
        for val in (float('nan'),float('inf'),0,-1,.2):
            with self.assertRaises(ValueError):
                self.api.case_witnesses(self.case,[],near_radius=val)

    def test_outputs_consistent_and_no_identity_claim(self):
        report={'benchmark_id':74,'session_id':201,'ground_truth_total':149,
                'ai_total':149,'matched':143,'missed':6,'extra':6,
                'window_seconds':1.0,'near_gate_radius_normalized':.035,
                'cases':[self.api.case_witnesses(self.case,[self.point(100,-.01)])]}
        with tempfile.TemporaryDirectory() as tmp:
            self.api.write_report(report,Path(tmp))
            data=json.loads((Path(tmp)/'gate-coverage.json').read_text(encoding='utf-8'))
            with (Path(tmp)/'gate-coverage.csv').open(encoding='utf-8-sig',newline='') as fp:
                rows=list(csv.DictReader(fp))
            md=(Path(tmp)/'gate-coverage.md').read_text(encoding='utf-8')
            self.assertEqual(len(rows),1)
            self.assertIn('591.091',md)
            self.assertFalse(data['cases'][0]['auto_recount_permitted'])

    def test_missing_zip_fails_without_creating_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'out'
            code=self.api.main(['--export',str(Path(tmp)/'absent.zip'),'--output-dir',str(output)])
            self.assertEqual(code,2)
            self.assertFalse(output.exists())


if __name__=='__main__':
    unittest.main()
