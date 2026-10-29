"""Same-raw observed motion, independent from counting or ID handoff jumps."""
import copy
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.raw_motion_audit import (
    RawMotionAudit, RAW_MOTION_FRAME_LIMIT, RAW_MOTION_RECORD_LIMIT,
    RAW_MOTION_TRACKS_PER_FRAME,
)


def item(raw=10, x=10., y=10., tracking_id=77, velocity=(1., 0.)):
    return {'track_id': tracking_id, 'raw_track_id': raw,
            'rect': [x - 1., y - 1., x + 1., y + 1.],
            'measured_velocity': list(velocity)}


def row(frame, raw=10, x=10., y=10., time=None, tracking_id=77):
    return {'frame_index': frame,
            'source_time_seconds': frame / 25 if time is None else time,
            'gate_tracks': [item(raw, x, y, tracking_id)]}


def audit(rows, tracking_id=77):
    state = RawMotionAudit(tracking_id)
    for record in rows:
        state.observe(record)
    return state, state.finish()


class RawMotionAuditTests(unittest.TestCase):
    def test_id_handoff_jump_is_not_either_raw_tokens_motion(self):
        _, result = audit([row(1, 10, 10), row(2, 10, 12),
                           row(3, 20, 100), row(4, 20, 99)])
        self.assertEqual(result['status'], 'observed')
        self.assertIs(result['identity_proven'], False)
        self.assertEqual(result['scope'], 'same_raw_contiguous_observations')
        segments = result['segments']
        self.assertEqual([segment['raw_track_id'] for segment in segments], [10, 20])
        self.assertEqual([segment['rect_motion']['dx'] for segment in segments], [2., -1.])
        self.assertEqual([segment['sample_count'] for segment in segments], [2, 2])
        self.assertFalse(any('direction' in segment for segment in segments))

    def test_missing_source_frame_splits_even_an_unchanged_raw_token(self):
        _, result = audit([row(1, x=10), row(2, x=12), row(4, x=100), row(5, x=99)])
        self.assertEqual([(segment['first_frame'], segment['last_frame'])
                          for segment in result['segments']], [(1, 2), (4, 5)])
        self.assertEqual([segment['rect_motion']['dx'] for segment in result['segments']], [2., -1.])

    def test_unknown_raw_invalid_rectangle_and_missing_owner_break_segments(self):
        for middle in ({'track_id': 77, 'raw_track_id': None, 'rect': [1, 1, 3, 3]},
                       {'track_id': 77, 'raw_track_id': 10, 'rect': [math.nan, 1, 3, 3]},
                       item(tracking_id=88)):
            records = [row(1, x=10), row(2, x=12), row(3), row(4, x=100), row(5, x=99)]
            records[2]['gate_tracks'] = [middle]
            _, result = audit(records)
            self.assertEqual([(segment['first_frame'], segment['last_frame'])
                              for segment in result['segments']], [(1, 2), (4, 5)])

    def test_synthetic_audit_rows_do_not_count_as_observed_samples(self):
        synthetic = row(2, x=1000)
        synthetic['audit_only'] = True
        metadata = row(2, x=1000)
        metadata['kind'] = 'event_delivery'
        _, result = audit([row(1), synthetic, metadata, row(2, x=12)])
        self.assertEqual(result['segments'][0]['sample_count'], 2)
        self.assertEqual(result['segments'][0]['rect_motion']['dx'], 2.)

    def test_identical_repeated_frame_is_not_a_second_sample(self):
        first = row(1)
        _, result = audit([first, copy.deepcopy(first), row(2, x=12)])
        self.assertEqual(result['segments'][0]['sample_count'], 2)
        self.assertEqual(result['conflicting_frames'], 0)

    def test_conflicting_frame_or_duplicate_canonical_hides_all_segments(self):
        repeated = [row(1), row(2, x=12), row(2, x=13)]
        duplicate = [row(1), row(2, x=12)]
        duplicate[-1]['gate_tracks'].append(item(x=13))
        for records in (repeated, duplicate):
            _, result = audit(records)
            self.assertEqual(result['status'], 'unavailable')
            self.assertEqual(result['segments'], [])
            self.assertEqual(result['conflicting_frames'], 1)

    def test_out_of_order_frame_or_clock_is_unavailable(self):
        for records in ([row(2), row(1), row(3)],
                        [row(1, time=.10), row(2, time=.09), row(3, time=.12)],
                        [row(1, time=.10), row(2, time=.10)]):
            _, result = audit(records)
            self.assertEqual(result['status'], 'unavailable')
            self.assertEqual(result['segments'], [])
            self.assertEqual(result['out_of_order_frames'], 1)

    def test_static_and_negative_identity_samples_are_not_invented_crossings(self):
        _, result = audit([row(1, raw=-3, tracking_id=-7), row(2, raw=-3, tracking_id=-7)], -7)
        self.assertEqual(result['tracking_id'], -7)
        self.assertEqual(result['segments'][0]['rect_motion'],
                         {'dx': 0., 'dy': 0., 'gap_frames': 1, 'pixels_per_frame': [0., 0.]})
        _, singleton = audit([row(1)])
        self.assertEqual(singleton['status'], 'unavailable')
        self.assertEqual(singleton['segments'], [])

    def test_invalid_scalar_types_do_not_enter_motion_or_filtered_velocity(self):
        for invalid in (True, '1', math.inf, math.nan):
            bad = row(1)
            bad['frame_index'] = invalid
            _, result = audit([bad, row(2)])
            self.assertEqual(result['segments'], [])
        for raw in (True, '10', 2**53):
            _, result = audit([row(1, raw=raw), row(2, raw=raw)])
            self.assertEqual(result['segments'], [])
        records = [row(1), row(2)]
        records[1]['gate_tracks'][0]['measured_velocity'] = [math.inf, 0.]
        _, result = audit(records)
        self.assertIsNone(result['segments'][0]['filtered_velocity'])

    def test_bounds_are_explicit_and_keep_only_bounded_segments(self):
        state, result = audit([row(frame, x=float(frame + 10))
                               for frame in range(1, RAW_MOTION_FRAME_LIMIT + 2)])
        self.assertEqual(len(state.frames), RAW_MOTION_FRAME_LIMIT)
        self.assertTrue(result['truncated'])
        self.assertEqual(result['segments'][0]['sample_count'], RAW_MOTION_FRAME_LIMIT)
        records = [row(frame, raw=(frame - 1) // 2, x=float(frame + 10))
                   for frame in range(1, (RAW_MOTION_RECORD_LIMIT + 1) * 2 + 1)]
        _, result = audit(records)
        self.assertEqual(len(result['segments']), RAW_MOTION_RECORD_LIMIT)
        self.assertTrue(result['truncated'])
        limited = row(1)
        limited['gate_tracks'] = [item(tracking_id=i + 1000) for i in range(RAW_MOTION_TRACKS_PER_FRAME)] + [item()]
        _, result = audit([limited, row(2)])
        self.assertEqual(result['segments'], [])
        self.assertTrue(result['truncated'])

    def test_results_and_inputs_are_detached_and_no_free_text_is_retained(self):
        records = [row(1), row(2, x=12)]
        records[0]['secret_url'] = 'http://token@private/path'
        records[0]['gate_tracks'][0]['model'] = 'private-model'
        before = copy.deepcopy(records)
        state, result = audit(records)
        self.assertEqual(records, before)
        result['segments'][0]['rect_motion']['pixels_per_frame'][0] = 999
        result['segments'][0]['filtered_velocity'][0] = 999
        self.assertEqual(state.finish()['segments'][0]['rect_motion']['pixels_per_frame'], [2., 0.])
        self.assertNotIn('private', json.dumps(state.finish()))

    def test_actual_diagnose_trace_exposes_separate_raw_audit_without_changing_old_audit(self):
        import app.benchmark_trace as benchmark_trace
        records = [row(1, 10, 10), row(2, 10, 12), row(3, 20, 100), row(4, 20, 99)]
        with tempfile.TemporaryDirectory() as directory, patch.object(benchmark_trace, 'TRACE_ROOT', Path(directory)):
            benchmark_trace.trace_path(42).write_text(''.join(json.dumps(record) + '\n' for record in records))
            result = benchmark_trace.diagnose_trace(42, [.1], .2, tracking_ids=[77])
            other = benchmark_trace.diagnose_trace(42, [.1], .2, tracking_ids=[None])
        diagnosis = result['items'][0]
        self.assertEqual(diagnosis['raw_motion_audit']['segments'][0]['rect_motion']['dx'], 2.)
        self.assertEqual(diagnosis['raw_motion_audit']['segments'][1]['rect_motion']['dx'], -1.)
        self.assertEqual(diagnosis['observed_track_audit']['raw_id_handoffs'][0]['rect_displacement'], [88., 0.])
        self.assertNotIn('raw_motion_audit', other['items'][0])


if __name__ == '__main__':
    unittest.main()
