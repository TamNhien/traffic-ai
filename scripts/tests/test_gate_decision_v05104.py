"""Counter rejection provenance is not permission to edit GT or counts."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


def mod():
    spec=importlib.util.spec_from_file_location('gate_audit_104',Path(__file__).parents[1]/'audit-gate-coverage.py')
    api=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
    return api


class TestDecisionAudit(unittest.TestCase):
    def setUp(self):
        self.api=mod()
        self.case={'kind':'missed','case_id':1,'time_s':10.,'direction':'in','vehicle_type':'motorcycle'}

    def point(self,frame, signed, reason=None, owner=1):
        return dict(frame=frame,time=frame/25,track_id=owner,raw_track_id=owner,
                    label='motorcycle',u=.5,signed=signed,primary_gate_decision=reason,
                    secondary_gate_rejection=None)

    def test_legacy_trace_never_invents_rejection_reason(self):
        row=self.api.case_witnesses(self.case,[self.point(100,-.01),self.point(101,.01)])
        self.assertEqual(row['gate_decision_provenance'],'not-recorded-in-export')
        self.assertEqual(row['finite_segment_span_candidates'],1)
        self.assertFalse(row['auto_recount_permitted'])

    def test_new_trace_shows_observed_primary_gate_decisions_only(self):
        row=self.api.case_witnesses(self.case,[self.point(100,-.01,'no-opposite-side-observation'),
                                                   self.point(101,.01,'outside-road-corridor')])
        self.assertEqual(row['gate_decision_provenance'],'per-track-present')
        self.assertEqual(row['nearest_tracks'][0]['primary_gate_decisions'],
            {'no-opposite-side-observation':1,'outside-road-corridor':1})
        self.assertEqual(row['nearest_tracks'][0]['decision_samples'],2)
        self.assertFalse(row['physical_identity_proven'])

    def test_two_tracks_are_kept_separate(self):
        row=self.api.case_witnesses(self.case,[self.point(100,-.01,'cooldown',owner=1),
             self.point(101,.01,'outside-finite-gate',owner=2)])
        self.assertEqual(row['near_gate_tracks'],2)
        self.assertEqual(row['finite_segment_span_candidates'],0)

    def test_secondary_rejection_does_not_automatically_count(self):
        values=[self.point(100,-.01,'no-opposite-side-observation'),self.point(101,.01,'no-opposite-side-observation')]
        values[-1]['secondary_gate_rejection']='same-direction'
        row=self.api.case_witnesses(self.case,values)
        self.assertEqual(row['nearest_tracks'][0]['secondary_gate_rejections'],{'same-direction':1})
        self.assertFalse(row['auto_recount_permitted'])

    def test_export_formats_retain_trace_absence_and_per_track_decisions(self):
        row=self.api.case_witnesses(self.case,[self.point(100,-.01,'cooldown')])
        row['road_tracks_zero_frames']=4
        report=dict(benchmark_id=75,session_id=202,ground_truth_total=149,ai_total=149,
                    matched=143,missed=6,extra=6,window_seconds=1.,near_gate_radius_normalized=.035,cases=[row])
        with tempfile.TemporaryDirectory() as td:
            self.api.write_report(report,Path(td))
            body=json.loads((Path(td)/'gate-coverage.json').read_text(encoding='utf-8'))
            csv=(Path(td)/'gate-coverage.csv').read_text(encoding='utf-8-sig')
            md=(Path(td)/'gate-coverage.md').read_text(encoding='utf-8')
            self.assertEqual(body['cases'][0]['near_gate_tracks'],1)
            self.assertIn('cooldown',csv)
            self.assertIn('cooldown',md)

    def test_no_tracks_remain_undetermined_even_if_road_tracks_zero(self):
        row=self.api.case_witnesses(self.case,[])
        self.assertEqual(row['gate_decision_provenance'],'not-recorded-in-export')
        self.assertEqual(row['near_gate_tracks'],0)
        self.assertFalse(row['auto_recount_permitted'])


if __name__=='__main__': unittest.main()
