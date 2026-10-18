"""Read-only report tests for V0.5.102. Verified archive test in user evidence run."""
import importlib.util
from pathlib import Path
import unittest
import tempfile


def module():
    path=Path(__file__).parents[1]/'audit-temporal-neighbors.py'
    spec=importlib.util.spec_from_file_location('temporal_neighbors_v05102',path)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TemporalNeighborTests(unittest.TestCase):
    def setUp(self):
        self.api=module()
        self.missed=[{'ground_truth_id':1,'time':392.179,'direction':'out','vehicle_type':'motorcycle'},
                     {'ground_truth_id':2,'time':591.091,'direction':'in','vehicle_type':'bicycle'}]
        self.extra=[{'ai_event_id':200,'time':393.303,'direction':'out','vehicle_type':'motorcycle'}]
        self.events=[{'id':200,'source_time_seconds':393.303,'direction':'out','vehicle_type':'motorcycle'}]
        self.gt=[{'id':1,'source_time_seconds':392.179,'direction':'out','vehicle_type':'motorcycle'},
                 {'id':2,'source_time_seconds':591.091,'direction':'in','vehicle_type':'bicycle'}]

    def calculate(self,matched=None):
        return self.api.candidates(self.missed,self.extra,matched or [],self.events,self.gt,tolerance=.75)

    def test_outside_window_suggests_review_not_auto_match(self):
        row=self.calculate()[0]
        assert row['kind']=='missed'
        assert row['review_category']=='outside_tolerance_same_direction_candidate'
        assert row['neighbors'][0]['delta_s']==1.124
        assert row['physical_identity_proven'] is False
        assert row['neighbors'][0]['within_scoring_window'] is False

    def test_no_nearby_event_is_not_marked_as_detector_failure(self):
        row=self.calculate()[2]
        assert row['time_s']==591.091
        assert row['neighbors']==[]
        assert row['review_category']=='no_matching_window_crossing'

    def test_candidate_claimed_by_other_gt_does_not_become_extra(self):
        missed=[{'ground_truth_id':11,'time':10.2,'direction':'in','vehicle_type':'motorcycle'}]
        events=[{'id':20,'source_time_seconds':10.0,'direction':'in','vehicle_type':'motorcycle'}]
        matched=[{'ai_event_id':20,'ground_truth_id':10}]
        rows=self.api.candidates(missed,[],matched,events,[],tolerance=.75)
        assert rows[0]['review_category']=='temporal_competition_not_identity_proof'
        assert rows[0]['neighbors'][0]['already_matched_to']==10

    def test_horizon_requires_finite_and_bounded(self):
        for value in (.75,-1,float('nan'),float('inf'),10):
            with self.assertRaises(ValueError):
                self.api.candidates([],[],[],[],[],tolerance=.75,horizon=value)

    def test_duplicate_assignment_fails_closed(self):
        matched=[{'ai_event_id':20,'ground_truth_id':1},{'ai_event_id':20,'ground_truth_id':2}]
        with self.assertRaises(ValueError):
            self.api.candidates([],[],matched,[],[],tolerance=.75)

    def test_export_json_csv_md_consistency(self):
        result=dict(format='traffic-ai-verified-temporal-neighbors',benchmark_id=73,session_id=200,
                    ground_truth_total=149,ai_total=149,matched=143,missed=6,extra=6,
                    tolerance_seconds=.75,search_horizon_seconds=2.0,
                    cases=self.calculate(),verified_trace_sha256='a'*64)
        with tempfile.TemporaryDirectory() as tmp:
            self.api.write(result,Path(tmp))
            import json,csv
            stored=json.loads((Path(tmp)/'temporal-neighbors.json').read_text(encoding='utf-8'))
            with (Path(tmp)/'temporal-neighbors.csv').open(encoding='utf-8-sig', newline='') as fp:
                csvrows=list(csv.DictReader(fp))
            md=(Path(tmp)/'temporal-neighbors.md').read_text(encoding='utf-8')
            assert len(stored['cases'])==3
            assert len(csvrows)==3
            assert '392.179' in md and '591.091' in md


if __name__=='__main__':
    unittest.main()
