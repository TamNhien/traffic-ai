"""Pure wire projection and production attach seam; no HTTP/ORM execution."""
import ast
import copy
import json
import math
from pathlib import Path
import unittest

from app.raw_motion_audit import scope_raw_motion_audit


def segment(raw=88, first=10, last=12, start=.36, end=.44, dx=-8., dy=-16.):
    gap = last - first
    return {'raw_track_id': raw, 'first_frame': first, 'last_frame': last,
            'first_time': start, 'last_time': end, 'sample_count': gap + 1,
            'rect_motion': {'dx': dx, 'dy': dy, 'gap_frames': gap,
                            'pixels_per_frame': [dx / gap, dy / gap]},
            'filtered_velocity': [20., 30.]}


def audit():
    return {'schema_version': 1, 'scope': 'same_raw_contiguous_observations',
            'tracking_id': 77, 'identity_proven': False, 'status': 'observed',
            'segments': [segment()], 'truncated': False, 'conflicting_frames': 0,
            'out_of_order_frames': 0, 'records_limit': 8}


def attach_function():
    path = Path(__file__).parents[1] / 'app/api/routes.py'
    tree = ast.parse(path.read_text())
    node = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name == '_attach_benchmark_trace_diagnosis')
    namespace = {'scope_raw_motion_audit': scope_raw_motion_audit}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                 str(path), 'exec'), namespace)
    return namespace['_attach_benchmark_trace_diagnosis']


class RawMotionScopeTests(unittest.TestCase):
    def test_valid_observed_same_raw_motion_keeps_filtered_velocity_independent(self):
        source = audit()
        result = scope_raw_motion_audit(source, 77)
        self.assertEqual(result, source)
        self.assertEqual(result['segments'][0]['rect_motion']['pixels_per_frame'], [-4., -8.])
        self.assertEqual(result['segments'][0]['filtered_velocity'], [20., 30.])
        self.assertIs(result['identity_proven'], False)

    def test_owner_scope_identity_and_schema_must_match_exactly(self):
        for key, value in [('tracking_id', 78), ('schema_version', True),
                           ('schema_version', 2), ('scope', 'whole_track_motion'),
                           ('identity_proven', True), ('status', 'complete')]:
            with self.subTest(key=key, value=value):
                source = audit()
                source[key] = value
                self.assertIsNone(scope_raw_motion_audit(source, 77))
        for owner in (None, True, '77', 2**53):
            self.assertIsNone(scope_raw_motion_audit(audit(), owner))

    def test_negative_synthetic_ids_and_time_zero_are_valid(self):
        source = audit()
        source['tracking_id'] = -7
        source['segments'] = [segment(raw=-9, first=1, last=3, start=0., end=.08)]
        self.assertEqual(scope_raw_motion_audit(source, -7), source)

    def test_unknown_fields_and_secrets_are_never_forwarded(self):
        source = audit()
        source['token'] = 'private-token'
        source['segments'][0]['path'] = '/private/secret'
        source['segments'][0]['rect_motion']['url'] = 'http://private/token'
        result = scope_raw_motion_audit(source, 77)
        encoded = json.dumps(result)
        self.assertNotIn('private', encoded)
        self.assertNotIn('token', encoded)
        self.assertNotIn('url', result['segments'][0]['rect_motion'])

    def test_only_consecutive_multi_sample_segments_are_accepted(self):
        for key, value in [('sample_count', 2), ('sample_count', True),
                           ('sample_count', 257), ('first_frame', True),
                           ('first_frame', 0), ('last_frame', 10),
                           ('raw_track_id', None), ('raw_track_id', 2**53)]:
            with self.subTest(key=key, value=value):
                source = audit()
                source['segments'][0][key] = value
                self.assertIsNone(scope_raw_motion_audit(source, 77))

    def test_timestamps_are_finite_nonnumeric_bools_and_backwards_values_rejected(self):
        for key, value in [('first_time', True), ('first_time', '0.36'),
                           ('first_time', -.01), ('last_time', .36),
                           ('last_time', math.nan), ('last_time', math.inf)]:
            with self.subTest(key=key, value=value):
                source = audit()
                source['segments'][0][key] = value
                self.assertIsNone(scope_raw_motion_audit(source, 77))

    def test_motion_gap_and_per_frame_vector_must_agree_with_bounds(self):
        for key, value in [('gap_frames', 3), ('gap_frames', True),
                           ('dx', '8'), ('dy', math.nan), ('dx', 1_000_001),
                           ('pixels_per_frame', [-4., 8.]),
                           ('pixels_per_frame', [False, -8.]),
                           ('pixels_per_frame', [-4.])]:
            with self.subTest(key=key, value=value):
                source = audit()
                source['segments'][0]['rect_motion'][key] = value
                self.assertIsNone(scope_raw_motion_audit(source, 77))
        source = audit()
        source['segments'][0]['filtered_velocity'] = ['private', 0.]
        self.assertIsNone(scope_raw_motion_audit(source, 77))

    def test_independent_six_decimal_rounding_is_not_a_motion_contradiction(self):
        source = audit()
        source['segments'] = [segment(first=1, last=4, start=0., end=.12, dx=1., dy=-2.)]
        source['segments'][0]['rect_motion']['pixels_per_frame'] = [.333333, -.666667]
        self.assertIsNotNone(scope_raw_motion_audit(source, 77))

    def test_segments_stay_disjoint_and_raw_reappearance_is_separate(self):
        source = audit()
        source['segments'].append(segment(raw=99, first=20, last=22, start=.76, end=.84))
        source['segments'].append(segment(raw=88, first=30, last=32, start=1.16, end=1.24))
        self.assertEqual(len(scope_raw_motion_audit(source, 77)['segments']), 3)
        for key, value in [('first_frame', 11), ('first_time', .4)]:
            changed = copy.deepcopy(source)
            changed['segments'][1][key] = value
            self.assertIsNone(scope_raw_motion_audit(changed, 77))

    def test_record_and_frame_bounds_do_not_forward_oversized_evidence(self):
        source = audit()
        source['segments'] *= 9
        self.assertIsNone(scope_raw_motion_audit(source, 77))
        source = audit()
        source['segments'] = [segment(first=1, last=200, start=0., end=7.96),
                              segment(first=210, last=309, start=8.36, end=12.32)]
        self.assertIsNone(scope_raw_motion_audit(source, 77))
        for key, value in [('records_limit', 9), ('records_limit', True),
                           ('truncated', 'yes'), ('conflicting_frames', 257),
                           ('out_of_order_frames', False)]:
            changed = audit()
            changed[key] = value
            self.assertIsNone(scope_raw_motion_audit(changed, 77))

    def test_conflict_or_out_of_order_cannot_appear_as_observed_motion(self):
        for key in ('conflicting_frames', 'out_of_order_frames'):
            source = audit()
            source[key] = 1
            self.assertIsNone(scope_raw_motion_audit(source, 77))
            source['status'] = 'unavailable'
            source['segments'] = []
            self.assertEqual(scope_raw_motion_audit(source, 77), source)
        source = audit()
        source['segments'] = []
        self.assertIsNone(scope_raw_motion_audit(source, 77))

    def test_unavailable_and_missing_values_remain_unknown(self):
        source = audit()
        source.update(status='unavailable', segments=[], truncated=True)
        self.assertEqual(scope_raw_motion_audit(source, 77), source)
        for value in (None, [], 'private', {'scope': 'same_raw_contiguous_observations'}):
            self.assertIsNone(scope_raw_motion_audit(value, 77))

    def test_projection_detaches_vectors_without_mutating_original(self):
        source = audit()
        before = copy.deepcopy(source)
        result = scope_raw_motion_audit(source, 77)
        result['segments'][0]['rect_motion']['pixels_per_frame'][0] = 99
        result['segments'][0]['filtered_velocity'][0] = 99
        self.assertEqual(source, before)

    def test_actual_attach_function_scopes_audit_and_legacy_absence_is_unchanged(self):
        attach = attach_function()
        item = {'ai_tracking_id': 77}
        diagnosis = {'reason': 'no_trace_window', 'raw_motion_audit': audit()}
        attach(item, diagnosis)
        self.assertEqual(item['diagnosis']['raw_motion_audit'], audit())
        self.assertEqual(item['diagnosis']['bicycle_context_scope'], 'matched_track')
        diagnosis['raw_motion_audit']['tracking_id'] = 78
        attach(item, diagnosis)
        self.assertNotIn('raw_motion_audit', item['diagnosis'])
        self.assertIn('raw_motion_audit', diagnosis)
        legacy = {'reason': 'no_trace_window'}
        attach(item, legacy)
        self.assertEqual(item['diagnosis'], {**legacy, 'bicycle_context_scope': 'matched_track'})
        nearby = {}
        attach(nearby, {'raw_motion_audit': audit()})
        self.assertNotIn('raw_motion_audit', nearby['diagnosis'])


if __name__ == '__main__':
    unittest.main()
