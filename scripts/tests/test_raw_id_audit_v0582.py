"""Guard source and audit helper remain compatible without AI/GPU dependencies."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('raw_id_audit_v0582', ROOT / 'scripts' / 'raw-id-audit.py')
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)
TRACK_SPEC = importlib.util.spec_from_file_location('v0582_independent_track_module', ROOT / 'ai-service' / 'app' / 'tracking.py')
track_module = importlib.util.module_from_spec(TRACK_SPEC)
sys.modules[TRACK_SPEC.name] = track_module
TRACK_SPEC.loader.exec_module(track_module)
TrackContinuityResolver = track_module.TrackContinuityResolver


class RawIdGuardTests(unittest.TestCase):
    def test_guard_and_audit_agree_on_precise_near_jump(self):
        prev = {'raw_track_id': 101, 'track_id': 101, 'frame_index': 10,
                'source_time_seconds': 0.36, 'center': [100., 100.], 'rect': [90., 90., 120., 120.]}
        now = {'raw_track_id': 101, 'track_id': 101, 'frame_index': 11,
               'source_time_seconds': 0.40, 'center': [900., 700.], 'rect': [880., 680., 925., 725.]}
        assert audit.jump_record(prev, now, 1440, 811, .18)
        r = TrackContinuityResolver()
        original, _ = r.resolve(101, tuple(prev['center']), 'motorcycle', 10, 1440, 811, rect=tuple(prev['rect']))
        new, _ = r.resolve(101, tuple(now['center']), 'motorcycle', 11, 1440, 811, rect=tuple(now['rect']))
        self.assertNotEqual(original, new)
        self.assertEqual(r.raw_id_discontinuities, 1)

    def test_long_gap_and_box_expansion_not_flagged(self):
        prev = {'raw_track_id': 3, 'track_id': 3, 'frame_index': 10,
                'source_time_seconds': 0.36, 'center': [100., 100.], 'rect': [90., 90., 120., 120.]}
        now = dict(prev, frame_index=20, source_time_seconds=.76,
                   center=[900., 700.], rect=[880., 680., 925., 725.])
        self.assertIsNone(audit.jump_record(prev, now, 1440, 811, .18))
        now = dict(prev, frame_index=11, source_time_seconds=.4,
                   center=[900., 700.], rect=[80., 80., 950., 750.])
        self.assertIsNone(audit.jump_record(prev, now, 1440, 811, .18))

    def test_dashboard_and_trace_expose_new_counter(self):
        for p in ('ai-service/app/runtime.py', 'ai-service/app/worker.py', 'frontend/src/main.jsx'):
            self.assertIn('raw_id_discontinuities', (ROOT / p).read_text(encoding='utf-8'), p)
        self.assertIn('raw_reuse_jump_ratio', (ROOT / 'ai-service/app/tracking.py').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
