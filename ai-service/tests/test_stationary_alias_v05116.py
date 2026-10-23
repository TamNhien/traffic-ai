"""Stationary identity ownership regressions; run with stdlib unittest.

No detector, network, benchmark archive or third-party test package is needed.
The historical coordinates below are rounded trace observations, not GT labels.
"""
from __future__ import annotations

import unittest

from app.tracking import TrackContinuityResolver


def box(point=(500.0, 300.0), width=80.0, height=96.0):
    return (point[0] - width / 2, point[1] - height / 2,
            point[0] + width / 2, point[1] + height / 2)


def observe(resolver, raw=10, point=(500.0, 300.0), frame=1, label="motorcycle", rect="default", claimed=None):
    if rect == "default":
        rect = box(point)
    return resolver.resolve(raw, point, label, frame, 1440, 811, claimed, rect=rect)


def parked(resolver, frames=(1, 7, 13), raw=10, label="motorcycle"):
    for frame in frames:
        observe(resolver, raw=raw, frame=frame, label=label)


def newcomer(resolver, frame=34, label="motorcycle", point=(600.0, 700.0), rect="default"):
    if rect == "default":
        rect = box(point, 180.0, 160.0)
    return observe(resolver, raw=20, point=point, frame=frame, label=label, rect=rect)


class StationaryOwnershipTests(unittest.TestCase):
    def test_distant_newcomer_cannot_borrow_parked_identity(self):
        resolver = TrackContinuityResolver()
        parked(resolver)
        self.assertEqual(newcomer(resolver), (20, False))
        self.assertEqual(resolver.stationary_alias_rejections, 1)
        self.assertEqual(resolver.short_gap_alias_rejections, 0)
        self.assertEqual(resolver.lineage_size(10), 1)

    def test_disabled_flag_restores_previous_alias(self):
        resolver = TrackContinuityResolver(stationary_alias_guard=False)
        parked(resolver)
        self.assertEqual(newcomer(resolver), (10, True))
        self.assertEqual(resolver.stationary_alias_rejections, 0)
        self.assertFalse(resolver._stationary_ownership)

    def test_stationary_guard_is_independent_of_short_gap_toggle(self):
        resolver = TrackContinuityResolver(short_gap_alias_guard=False)
        parked(resolver)
        self.assertEqual(newcomer(resolver), (20, False))

    def test_new_window_starts_at_thirteen_and_ends_at_normal_gap(self):
        for gap, rejected in ((12, False), (13, True), (30, True), (31, False)):
            with self.subTest(gap=gap):
                resolver = TrackContinuityResolver(max_distance_ratio=.20)
                parked(resolver)
                result = newcomer(resolver, frame=13 + gap)
                self.assertEqual(resolver.stationary_alias_rejections, int(rejected))
                self.assertEqual(result, (10, True) if gap == 12 else (20, False))

    def test_two_observations_are_insufficient_even_when_span_is_long(self):
        resolver = TrackContinuityResolver()
        parked(resolver, frames=(1, 13))
        self.assertEqual(newcomer(resolver), (10, True))

    def test_three_observations_need_twelve_distinct_frames_of_span(self):
        resolver = TrackContinuityResolver()
        parked(resolver, frames=(10, 11, 13))
        self.assertEqual(newcomer(resolver), (10, True))

    def test_duplicate_and_stale_clocks_cannot_manufacture_evidence(self):
        resolver = TrackContinuityResolver()
        parked(resolver, frames=(1, 1, 1, 13, 3, 13))
        episode = resolver._stationary_ownership[10]
        self.assertEqual((episode.first_frame, episode.last_frame, episode.observations), (1, 13, 2))
        self.assertEqual(newcomer(resolver), (10, True))

    def test_dense_hundred_frame_history_keeps_episode_span_and_bounded_count(self):
        resolver = TrackContinuityResolver()
        for frame in range(1, 101):
            observe(resolver, frame=frame, point=(500 + (frame % 2) * .1, 300.0))
        episode = resolver._stationary_ownership[10]
        self.assertEqual((episode.first_frame, episode.last_frame, episode.observations), (1, 100, 3))
        self.assertLessEqual(episode.max_drift, .101)
        self.assertEqual(newcomer(resolver, frame=121), (20, False))

    def test_close_handoff_remains_stitched(self):
        resolver = TrackContinuityResolver()
        parked(resolver)
        self.assertEqual(newcomer(resolver, point=(610, 330)), (10, True))
        self.assertEqual(resolver.stationary_alias_rejections, 0)

    def test_large_perspective_growth_requires_prediction_contradiction_too(self):
        resolver = TrackContinuityResolver()
        parked(resolver)
        point = (600, 700)
        self.assertEqual(newcomer(resolver, point=point, rect=box(point, 320, 320)), (10, True))
        self.assertEqual(resolver.stationary_alias_rejections, 0)

    def test_coherent_fast_motion_remains_stitched(self):
        resolver = TrackContinuityResolver()
        for frame, x in ((1, 100), (7, 160), (13, 220)):
            observe(resolver, frame=frame, point=(x, 300))
        self.assertEqual(newcomer(resolver, point=(400, 300)), (10, True))
        self.assertEqual(resolver.stationary_alias_rejections, 0)

    def test_previously_established_heading_excludes_a_stopped_moving_track(self):
        resolver = TrackContinuityResolver()
        for frame in range(1, 7):
            observe(resolver, frame=frame, point=(480 + frame * 4, 300))
        for frame in range(7, 100):
            observe(resolver, frame=frame, point=(504, 300))
        self.assertIn(10, resolver._anchor_velocities)
        self.assertEqual(newcomer(resolver, frame=120), (10, True))
        self.assertEqual(resolver.stationary_alias_rejections, 0)

    def test_four_wheel_rules_are_unchanged(self):
        for label in ("car", "truck", "bus"):
            with self.subTest(label=label):
                resolver = TrackContinuityResolver(heavy_max_gap_frames=90)
                parked(resolver, label=label)
                self.assertEqual(newcomer(resolver, label=label), (10, True))
                self.assertEqual(resolver.stationary_alias_rejections, 0)

    def test_bicycle_and_motorcycle_share_stationary_family_evidence(self):
        resolver = TrackContinuityResolver()
        parked(resolver, label="bicycle")
        self.assertEqual(newcomer(resolver), (20, False))

    def test_same_raw_return_does_not_enter_newcomer_guard(self):
        resolver = TrackContinuityResolver()
        parked(resolver)
        point = (600, 700)
        self.assertEqual(observe(resolver, raw=10, point=point, frame=34, rect=box(point, 180, 160)), (10, False))
        self.assertEqual(resolver.stationary_alias_rejections, 0)

    def test_rejected_newcomer_preserves_incumbent_return(self):
        resolver = TrackContinuityResolver()
        parked(resolver)
        self.assertEqual(newcomer(resolver), (20, False))
        self.assertEqual(observe(resolver, frame=35, claimed={20}), (10, False))

    def test_invalid_or_missing_box_discards_ownership_evidence(self):
        for rect in (None, (0, 0, 0, 5), (0, 5, 1, 0), (0, 0, float("nan"), 5)):
            with self.subTest(rect=rect):
                resolver = TrackContinuityResolver()
                parked(resolver)
                observe(resolver, frame=14, rect=rect)
                self.assertNotIn(10, resolver._stationary_ownership)
                self.assertEqual(newcomer(resolver, frame=35), (10, True))

    def test_invalid_new_box_cannot_trigger_stationary_rejection(self):
        resolver = TrackContinuityResolver()
        parked(resolver)
        self.assertEqual(newcomer(resolver, rect=None), (10, True))
        self.assertEqual(resolver.stationary_alias_rejections, 0)

    def test_long_same_raw_gap_restarts_evidence(self):
        resolver = TrackContinuityResolver()
        parked(resolver)
        observe(resolver, frame=44)
        episode = resolver._stationary_ownership[10]
        self.assertEqual((episode.first_frame, episode.observations), (44, 1))
        self.assertEqual(newcomer(resolver, frame=65), (10, True))

    def test_motion_outside_episode_quarter_footprint_restarts_evidence(self):
        resolver = TrackContinuityResolver()
        parked(resolver)
        observe(resolver, frame=43, point=(533, 300))
        episode = resolver._stationary_ownership[10]
        self.assertEqual((episode.first_frame, episode.observations), (43, 1))

    def test_episode_keeps_old_drift_after_dense_recent_stationarity(self):
        resolver = TrackContinuityResolver()
        observe(resolver, frame=1)
        observe(resolver, frame=13, point=(520, 300))
        for frame in range(14, 114):
            observe(resolver, frame=frame, point=(520, 300))
        episode = resolver._stationary_ownership[10]
        self.assertEqual(episode.first_frame, 1)
        self.assertEqual(episode.max_drift, 20)
        # A smaller valid owner box makes the retained drift incompatible.
        observe(resolver, frame=114, point=(520, 300), rect=box((520, 300), 40, 40))
        self.assertEqual(resolver._stationary_ownership[10].first_frame, 114)

    def test_explicit_alias_fusion_clears_both_certificates(self):
        resolver = TrackContinuityResolver()
        parked(resolver)
        for frame in (1, 7, 13):
            observe(resolver, raw=30, frame=frame, point=(100, 100), claimed={10})
        self.assertEqual(set(resolver._stationary_ownership), {10, 30})
        self.assertEqual(resolver.alias_raw_id(30, 10), 30)
        self.assertNotIn(10, resolver._stationary_ownership)
        self.assertNotIn(30, resolver._stationary_ownership)

    def test_new_raw_alias_starts_independent_episode(self):
        resolver = TrackContinuityResolver()
        parked(resolver)
        self.assertEqual(newcomer(resolver, point=(501, 300)), (10, True))
        episode = resolver._stationary_ownership[10]
        self.assertEqual((episode.raw_id, episode.first_frame, episode.observations), (20, 34, 1))

    def test_ttl_cleanup_releases_certificate_with_identity(self):
        resolver = TrackContinuityResolver()
        parked(resolver)
        observe(resolver, raw=30, frame=300, point=(100, 100))
        self.assertNotIn(10, resolver._stationary_ownership)
        self.assertNotIn(10, resolver._states)
        self.assertNotIn(10, resolver._raw_to_canonical)

    def test_actual_rounded_session_210_parked_owner_rejects_raw_145089(self):
        observations = [
            (9690, (1116.156, 281.006, 1214.398, 367.868)),
            (9691, (1115.954, 281.095, 1213.823, 367.630)),
            (9693, (1117.222, 282.405, 1213.480, 367.508)),
            (9694, (1116.289, 280.052, 1214.625, 367.206)),
            (9702, (1117.503, 283.673, 1212.063, 367.074)),
            (9703, (1117.640, 284.419, 1211.850, 367.089)),
            (9704, (1117.084, 283.901, 1212.380, 367.344)),
            (9721, (1116.858, 282.224, 1214.109, 367.699)),
            (9730, (1117.177, 282.538, 1213.847, 367.680)),
            (9731, (1117.145, 282.430, 1213.871, 367.811)),
            (9752, (1117.347, 284.423, 1212.168, 367.689)),
        ]
        newcomer_box = (1171.362, 647.250, 1351.938, 808.800)
        for enabled, expected in ((False, (143964, True)), (True, (145089, False))):
            with self.subTest(enabled=enabled):
                resolver = TrackContinuityResolver(stationary_alias_guard=enabled)
                for frame, rect in observations:
                    point = ((rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2)
                    observe(resolver, raw=143964, frame=frame, point=point, rect=rect)
                point = ((newcomer_box[0] + newcomer_box[2]) / 2, (newcomer_box[1] + newcomer_box[3]) / 2)
                self.assertEqual(observe(resolver, raw=145089, frame=9773, point=point, rect=newcomer_box), expected)
                self.assertEqual(resolver.stationary_alias_rejections, int(enabled))


if __name__ == "__main__":
    unittest.main()
