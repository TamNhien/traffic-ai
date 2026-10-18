"""Regression tests for verified, non-mutating passage-evidence worklists."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'audit-error-evidence.py'
spec = importlib.util.spec_from_file_location('passage_evidence_v0599', SOURCE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def fixture():
    return {
        'format': 'traffic-ai-gt-case-forensics', 'version': 1,
        'session_id': 198, 'benchmark_id': 71, 'ground_truth_total': 3,
        'ai_total': 3, 'matched': 2, 'missed': 1, 'extra': 1,
        'trace_available': True, 'source_trace_sha256': 'a' * 64,
        'cases': [
            {'kind': 'missed', 'time': 59.446, 'direction': 'in',
             'vehicle_type': 'motorcycle', 'ground_truth_id': 1, 'ai_event_id': None,
             'report_evidence': {'status': 'persisted_event_claimed_by_other_gt',
                                 'nearby_persisted_events': [{'ai_event_id': 8, 'assigned_ground_truth_id': 2}]},
             'trace_evidence': {'frames': 50, 'tracks_both_sides': 1, 'near_line_tracks': 2,
                                'tracks': {'17': {'samples': 8, 'near_line_samples': 4,
                                                  'side_negative': True, 'side_positive': True}},
                                'proposals': [], 'deliveries': []}},
            {'kind': 'extra', 'time': 491.92, 'direction': 'out',
             'vehicle_type': 'motorcycle', 'ai_event_id': 9, 'ground_truth_id': None,
             'diagnostic_reason': 'spatial_duplicate_near_gt',
             'trace_evidence': {'frames': 51, 'tracks_both_sides': 2, 'near_line_tracks': 2,
                                'tracks': {}, 'proposals': [], 'deliveries': []}},
        ],
    }


class PassageEvidenceTests(unittest.TestCase):
    def test_temporal_claim_is_review_not_diagnosed_detector_miss(self):
        output = audit.make_worklist(fixture())
        self.assertEqual(output['category_counts']['temporal_assignment_conflict'], 1)
        self.assertEqual(output['cases'][0]['nearby_assigned_event_ids'], [8])
        self.assertEqual(output['cases'][0]['nearby_assigned_gt_ids'], [2])
        self.assertFalse(output['cases'][0]['physical_identity_proven'])

    def test_nearby_two_sided_track_never_implies_identity_or_auto_count(self):
        f = fixture()
        original = json.dumps(f, sort_keys=True)
        result = audit.make_worklist(f)
        self.assertEqual(json.dumps(f, sort_keys=True), original)
        self.assertEqual((result['ground_truth_total'], result['ai_total'], result['matched']), (3, 3, 2))
        self.assertFalse(all(row['physical_identity_proven'] for row in result['cases']))
        self.assertEqual(result['cases'][0]['candidate_tracks'][0]['track_id'], '17')

    def test_extra_categories_are_not_suppression_licenses(self):
        f = fixture()
        f['cases'][1]['diagnostic_reason'] = 'rescued_gap_unmatched'
        self.assertEqual(audit.make_worklist(f)['cases'][1]['category'], 'gap_rescue_review')
        f['cases'][1]['diagnostic_reason'] = 'interpolated_unmatched'
        self.assertEqual(audit.make_worklist(f)['cases'][1]['category'], 'unmatched_crossing_review')

    def test_images_are_1_based_and_bound_to_verified_fps(self):
        images = [(1487, 'session_198_foo_frame_1487.jpg')]
        rows = audit.make_worklist(fixture(), images, 25.0)['cases']
        self.assertEqual(rows[0]['camera_image'], images[0][1])
        self.assertIsNone(rows[1]['camera_image'])
        self.assertAlmostEqual(rows[0]['camera_image_time_offset_seconds'], 0, places=2)
        with self.assertRaisesRegex(ValueError, 'FPS'):
            audit.make_worklist(fixture(), images, None)

    def test_invalid_or_incomplete_trace_fails_closed(self):
        bad = fixture()
        bad['trace_available'] = False
        with self.assertRaisesRegex(ValueError, 'verified'):
            audit.make_worklist(bad)
        bad = fixture()
        bad['missed'] = 2
        with self.assertRaisesRegex(ValueError, 'inconsistent'):
            audit.make_worklist(bad)

    def test_evidence_index_only_regular_jpg_and_no_symlink_escape(self):
        with tempfile.TemporaryDirectory() as t:
            folder = Path(t)
            (folder/'session_198_ok_frame_1487.jpg').write_bytes(b'x')
            (folder/'bad_frame_24.png').write_bytes(b'x')
            (folder/'bad_frame_3.jpg.exe').write_bytes(b'x')
            (folder/'outside_frame_999.jpg').symlink_to(folder/'session_198_ok_frame_1487.jpg')
            self.assertEqual(audit._image_index(folder), [(1487, 'session_198_ok_frame_1487.jpg')])

    def test_written_json_csv_md_are_consistent(self):
        with tempfile.TemporaryDirectory() as t:
            folder = Path(t)
            result = audit.make_worklist(fixture())
            audit.save(result, folder)
            self.assertEqual(json.loads((folder/'passage-evidence.json').read_text())['case_count'], 2)
            self.assertEqual(len((folder/'passage-evidence.csv').read_text(encoding='utf-8-sig').splitlines()), 3)
            self.assertIn('No event/GT is added', (folder/'passage-evidence.md').read_text())

    def test_timecodes_boundaries(self):
        self.assertEqual(audit._timecode(3600), '01:00:00.000')
        with self.assertRaises(ValueError):
            audit._timecode(float('nan'))
        with self.assertRaises(ValueError):
            audit._timecode(-1)

    def test_cli_failure_on_unverified_trace_preserves_output(self):
        with tempfile.TemporaryDirectory() as t:
            bad = fixture()
            bad['trace_available'] = False
            output = Path(t)/'does-not-exist'
            with patch.object(audit, '_forensics') as mock_loader:
                mock_loader.return_value.analyze.return_value = bad
                with patch('sys.stderr'):
                    self.assertEqual(audit.main(['--export', str(Path(t)/'dummy.zip'),
                                                 '--output-dir', str(output)]), 2)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
