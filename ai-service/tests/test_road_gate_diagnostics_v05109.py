"""Dependency-free real-geometry regression for V0.5.109 telemetry."""
import unittest
from app.counting import CountingLine, RoadZone
from app.road_gate_diagnostics import road_gate_probe

LINE = CountingLine(.2, .5, .8, .5)
ZONE = RoadZone(.2, .30, .8, .30, .8, .8, .2, .8)


class RoadGateDiagnostics(unittest.TestCase):
    def test_interior_counts_in_both_strict_and_margin(self):
        result = road_gate_probe((500, 500), LINE, ZONE, 1000, 1000, margin_ratio=.012)
        self.assertTrue(result['strict_road'])
        self.assertTrue(result['margin_eligible'])
        self.assertTrue(result['near_eligible_gate'])
        self.assertFalse(result['margin_only'])

    def test_margin_only_does_not_pretend_strict_or_count(self):
        result = road_gate_probe((795, 500), LINE, ZONE, 1000, 1000, margin_ratio=.012)
        self.assertTrue(result['strict_road'])
        result = road_gate_probe((806, 500), LINE, ZONE, 1000, 1000, margin_ratio=.012)
        self.assertFalse(result['strict_road'])
        self.assertTrue(result['margin_eligible'])
        self.assertTrue(result['margin_only'])
        self.assertTrue(result['near_finite_gate'])
        self.assertTrue(result['near_eligible_gate'])

    def test_near_infinite_extension_is_not_finite_gate(self):
        r = road_gate_probe((100, 500), LINE, None, 1000, 1000, margin_ratio=.012)
        self.assertFalse(r['near_finite_gate'])
        self.assertTrue(r['margin_eligible'])

    def test_outside_polygon_and_far_from_gate_not_eligible(self):
        r = road_gate_probe((950, 130), LINE, ZONE, 1000, 1000, margin_ratio=.012)
        self.assertFalse(r['strict_road'])
        self.assertFalse(r['margin_eligible'])
        self.assertFalse(r['near_eligible_gate'])

    def test_no_road_zone_is_not_called_a_recovery(self):
        r = road_gate_probe((500, 500), LINE, None, 1000, 1000)
        self.assertTrue(r['strict_road'])
        self.assertTrue(r['margin_eligible'])
        self.assertFalse(r['margin_only'])

    def test_bad_data_fail_closed_without_counting(self):
        self.assertIsNone(road_gate_probe((float('nan'), 2), LINE, ZONE, 1000, 1000))
        self.assertIsNone(road_gate_probe((1, 2), LINE, ZONE, 0, 0))
        self.assertIsNone(road_gate_probe((1, 2), LINE, ZONE, 1000, 1000, margin_ratio=-1))


if __name__ == '__main__':
    unittest.main()
