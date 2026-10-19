"""Endpoint precision regression usable in Python slim without pytest."""
import unittest

from app.finite_endpoint_guard import endpoint_precision_rejection


LINE = ((0.343, 0.479), (0.7587, 0.385))


def cross_at(t):
    a, b = LINE
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def policy(t, signed=.01, direction='in', label='motorcycle', method='interpolated'):
    return endpoint_precision_rejection(LINE, cross_at(t), signed, direction, label, method)


class FiniteEndpointGuardTests(unittest.TestCase):
    def test_interpolated_endpoint_requires_center_evidence(self):
        self.assertIsNotNone(policy(.055, signed=.00))
        self.assertIsNotNone(policy(.076, signed=-.010, direction='out'))
        self.assertIsNone(policy(.08, signed=0))
        self.assertIsNone(policy(.055, signed=.051))
        self.assertIsNone(policy(.955, signed=-.051, direction='out'))

    def test_direct_rescued_heavy_and_interior_are_preserved(self):
        self.assertIsNone(policy(.01, method='direct'))
        self.assertIsNone(policy(.01, method='rescued'))
        self.assertIsNone(policy(.01, label='truck'))
        self.assertIsNone(policy(.01, label='car'))
        self.assertIsNone(policy(.3, signed=-.04))
        self.assertIsNone(policy(.955, signed=0))

    def test_fail_open_for_unknown_or_bad_geometry(self):
        self.assertIsNone(endpoint_precision_rejection(LINE, None, 0., 'in', 'motorcycle', 'interpolated'))
        self.assertIsNone(endpoint_precision_rejection(LINE, (.343, .479), None, 'in', 'motorcycle', 'interpolated'))
        self.assertIsNone(endpoint_precision_rejection(LINE, (.343, .479), float('nan'), 'in', 'motorcycle', 'interpolated'))
        self.assertIsNone(endpoint_precision_rejection(((0, 0), (0, 0)), (.343, .479), 0, 'in', 'motorcycle', 'interpolated'))
        self.assertIsNone(endpoint_precision_rejection(LINE, (.343, .479), 0, 'unknown', 'motorcycle', 'interpolated'))


if __name__ == '__main__':
    unittest.main()
