"""No Docker, GPU or production state is needed to test GT replay diagnosis."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

TARGET = Path(__file__).resolve().parents[1] / 'gt-replay-witness.py'
SPEC = importlib.util.spec_from_file_location('traffic_v0583_gt_replay', TARGET)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GTReplayWitnessTests(unittest.TestCase):
    def setUp(self):
        self.crossing = {'seconds': 290.064, 'frame': 7253,
                         'position': [0.450292, 0.454739], 'vehicle_type': 'motorcycle',
                         'direction': 'out', 'method': 'interpolated'}
        self.events = [{'id': 11680, 'source_time_seconds': 290.0639,
                        'crossing_x': .450292, 'crossing_y': .454739, 'direction': 'out'}]
        self.report = {'matched_items': [{'ai_event_id': 11680, 'ground_truth_id': 8247,
                        'ground_truth_time': 289.824, 'ground_truth_direction': 'in',
                        'ground_truth_vehicle_type': 'motorcycle',
                        'class_correct': True, 'direction_correct': False}]}

    def test_reports_lost_event_with_historic_wrong_direction(self):
        info = MODULE.classify_removed_events([self.crossing], self.report, self.events)[0]
        self.assertEqual(info['baseline_link'], 'historically_timecode_matched')
        self.assertEqual(info['baseline_ground_truth']['direction'], 'in')
        self.assertIs(info['direction_correct'], False)

    def test_reports_correct_direction_only_if_genuinely_matching(self):
        self.report['matched_items'][0]['direction_correct'] = True
        info = MODULE.classify_removed_events([self.crossing], self.report, self.events)[0]
        self.assertIs(info['direction_correct'], True)

    def test_does_not_infer_ground_truth_from_unmatched_baseline_event(self):
        info = MODULE.classify_removed_events([self.crossing], {'matched_items': []}, self.events)[0]
        self.assertEqual(info['baseline_link'], 'historically_unmatched_ai')
        self.assertIsNone(info['baseline_ground_truth'])

    def test_nearby_different_location_does_not_claim_gt(self):
        wrong = {**self.events[0], 'crossing_x': 0.7}
        info = MODULE.classify_removed_events([self.crossing], self.report, [wrong])[0]
        self.assertEqual(info['baseline_link'], 'unverified')

    def test_ambiguous_event_stays_unverified(self):
        info = MODULE.classify_removed_events([self.crossing], self.report,
                                               [self.events[0], {**self.events[0], 'id': 11681}])[0]
        self.assertEqual(info['baseline_link'], 'ambiguous_baseline_event')
        self.assertIsNone(info['direction_correct'])

    def test_markdown_does_not_claim_new_gt_accuracy(self):
        data = {'reference_session': 182, 'current_session': 183, 'reference_gt': 149,
                'reference_matched_timecode': 139, 'reference_wrong_direction': 3,
                'replay_summary': {'created_removed': 1, 'created_introduced': 0},
                'lost_event_witnesses': MODULE.classify_removed_events([self.crossing], self.report, self.events),
                'warning': 'Re-run the GT benchmark'}
        rendered = MODULE.markdown(data)
        self.assertIn('290.064s', rendered)
        self.assertIn('direction correct **False**', rendered)
        self.assertIn('not a replacement benchmark', rendered)

if __name__ == '__main__':
    unittest.main()
