"""V0.5.118 endpoint rescue policy; usable without inference dependencies."""
import math
import unittest

from app.finite_endpoint_guard import endpoint_precision_rejection


LINE = ((0.343, 0.479), (0.7587, 0.385))


def crossing_at(projection):
    a, b = LINE
    return tuple(a[i] + (b[i] - a[i]) * projection for i in range(2))


def reject(projection=.07, center=-.02, direction='out', label='motorcycle',
           method='rescued', enabled=True):
    return endpoint_precision_rejection(
        LINE, crossing_at(projection), center, direction, label, method,
        allow_rescued=enabled,
    )


class EndpointRescueTests(unittest.TestCase):
    def test_rescue_requires_explicit_extension_and_keeps_recorded_method(self):
        self.assertIsNone(reject(enabled=False))
        result = reject()
        self.assertEqual(result['kind'], 'finite_endpoint_rescue_center_uncertain')
        self.assertEqual(result['method'], 'rescued')
        self.assertEqual(result['projection'], .07)
        self.assertEqual(result['edge_fraction'], .08)
        self.assertEqual(result['stable_center_side'], .04)

    def test_recorded_rescue_geometry_uses_unchanged_endpoint_thresholds(self):
        result = endpoint_precision_rejection(
            LINE, (.372487, .472332), -.021512, 'out', 'motorcycle', 'rescued',
            allow_rescued=True)
        self.assertEqual(result['projection'], .070934)
        self.assertEqual(result['center_signed'], -.021512)
        self.assertEqual(result['kind'], 'finite_endpoint_rescue_center_uncertain')

    def test_interpolated_contract_is_unchanged(self):
        for direction, center in [('in', .01), ('out', -.01)]:
            old = reject(direction=direction, center=center, method='interpolated', enabled=False)
            new = reject(direction=direction, center=center, method='interpolated')
            self.assertEqual(old, new)
            self.assertEqual(old['kind'], 'finite_endpoint_center_uncertain')

    def test_same_finite_start_bounds_in_both_directions(self):
        for label in ('bicycle', 'motorcycle'):
            for direction, center in [('in', .039), ('out', -.039)]:
                self.assertIsNotNone(reject(.079, center, direction, label))
                self.assertIsNone(reject(.081, center, direction, label))
                self.assertIsNone(reject(.95, center, direction, label))
                self.assertIsNone(reject(-.01, center, direction, label))
                self.assertIsNone(reject(1.01, center, direction, label))

    def test_clear_destination_center_preserves_genuine_return(self):
        self.assertIsNone(reject(center=.04, direction='in'))
        self.assertIsNone(reject(center=-.04, direction='out'))
        self.assertIsNone(reject(center=.10, direction='in'))
        self.assertIsNone(reject(center=-.10, direction='out'))

    def test_direct_unknown_and_four_wheel_are_preserved(self):
        for method in ('direct', 'unknown', None):
            self.assertIsNone(reject(method=method))
        for label in ('car', 'truck', 'bus', 'person', 'other'):
            self.assertIsNone(reject(label=label))
        self.assertIsNone(reject(direction='unknown'))

    def test_missing_nonfinite_and_invalid_geometry_fail_open(self):
        for xy, center in [(None, 0.), (crossing_at(.07), None),
                           ((math.nan, .5), 0.), ((.5, math.inf), 0.),
                           (crossing_at(.07), math.nan), ((-1., .5), 0.)]:
            self.assertIsNone(endpoint_precision_rejection(
                LINE, xy, center, 'out', 'motorcycle', 'rescued', allow_rescued=True))
        self.assertIsNone(endpoint_precision_rejection(
            ((.5, .5), (.5, .5)), (.5, .5), 0., 'out', 'bicycle', 'rescued', allow_rescued=True))

    def test_geometry_policy_has_no_vehicle_identity_or_clock_input(self):
        # Translation of a normalized finite segment preserves the decision;
        # runtime IDs and benchmark timestamps never enter the policy API.
        moved_line = tuple((x + .01, y + .02) for x, y in LINE)
        x, y = crossing_at(.07)
        result = endpoint_precision_rejection(
            moved_line, (x + .01, y + .02), -.02, 'out', 'motorcycle', 'rescued',
            allow_rescued=True)
        self.assertEqual(result, reject())


if __name__ == '__main__':
    unittest.main()
