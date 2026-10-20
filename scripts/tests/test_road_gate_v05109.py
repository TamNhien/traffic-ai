"""Read-only road probe integration contract (stdlib-only)."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

class Integration(unittest.TestCase):
    def test_worker_telemetry_and_trace_are_connected(self):
        w = (ROOT / 'ai-service/app/worker.py').read_text('utf-8')
        for token in ('road_gate_probe(', 'self.state.road_margin_eligible_tracks_current_frame += 1',
                      'self.state.near_gate_eligible_tracks_current_frame += 1',
                      '"road_margin_eligible_tracks":', '"near_gate_eligible_tracks":',
                      "gate_trace_track['road_gate_probe'] = road_probe"):
            self.assertIn(token,w)

    def test_ui_uses_tolerant_road_field_for_warning(self):
        u=(ROOT/'frontend/src/main.jsx').read_text('utf-8')
        self.assertIn('activePipeline.road_margin_eligible_tracks_current_frame',u)
        self.assertIn('Track gần đoạn vạch',u)

    def test_no_event_gt_or_counter_mutations_in_policy(self):
        source=(ROOT/'ai-service/app/road_gate_diagnostics.py').read_text('utf-8')
        self.assertNotIn('commit_crossing(',source)
        self.assertNotIn('reconcile(',source)
        self.assertNotIn('db.session',source)

    def test_old_exports_explicitly_keep_new_metrics_unknown(self):
        code=(ROOT/'scripts/audit-gate-coverage.py').read_text('utf-8')
        self.assertIn('if margin_samples else None',code)
        self.assertIn('if near_samples else None',code)

if __name__ == '__main__':
    unittest.main()
