"""Causal ownership and uncommitted lifecycle regression; stdlib-only."""
from dataclasses import replace
import unittest

from app.counting import (CountingLine, HeavyVehicleCrossingRescuer, LineCrossingCounter,
                          TwoWheelCenterCrossingRescuer, VerifiedAnchorSpanRescuer)
from app.fragment_ownership import FragmentObservation, TwoWheelFragmentOwnership
from app.tracking import TrackContinuityResolver


LINE = ((0., 200.), (1000., 200.))


def owner(frame):
    return FragmentObservation(10, 10, (100., 300. - frame * 4, 200., 500. - frame * 4), "motorcycle", 30, 3)


def child(frame):
    return FragmentObservation(20, 20, (130., 420. - frame * 4, 170., 480. - frame * 4), "motorcycle", max(0, frame - 7))


def seed(policy):
    for frame in range(8):
        policy.observe(frame, [owner(frame)], LINE, 1000, 800)


def certify(policy, transform=lambda item: item):
    result = None
    for frame in range(8, 11):
        result = policy.observe(frame, [owner(frame), transform(child(frame))], LINE, 1000, 800)
    return result


class FragmentOwnershipTests(unittest.TestCase):
    def test_three_distinct_fresh_views_certify_without_aliasing(self):
        policy = TwoWheelFragmentOwnership()
        seed(policy)
        filtered, proofs, releases = certify(policy)
        self.assertFalse(filtered)
        self.assertFalse(releases)
        self.assertEqual(len(proofs), 1)
        self.assertEqual(proofs[0]["sample_frames"], [8, 9, 10])
        self.assertEqual(proofs[0]["track_id"], 20)
        self.assertEqual(proofs[0]["owner_track_id"], 10)
        self.assertEqual(policy.retirements, 0)

    def test_two_frames_or_same_clock_repeats_never_certify(self):
        policy = TwoWheelFragmentOwnership()
        seed(policy)
        for frame in (8, 8, 8, 9, 9):
            self.assertFalse(policy.observe(frame, [owner(frame), child(frame)], LINE, 1000, 800)[1])

    def test_future_clock_gap_cannot_fill_missing_views(self):
        policy = TwoWheelFragmentOwnership()
        seed(policy)
        for frame in (8, 9, 20):
            self.assertFalse(policy.observe(frame, [owner(frame), child(frame)], LINE, 1000, 800)[1])

    def test_ambiguous_or_mixed_class_duplicate_raw_cannot_certify(self):
        for label in ("motorcycle", "car"):
            policy = TwoWheelFragmentOwnership()
            seed(policy)
            for frame in range(8, 11):
                rows = [owner(frame), child(frame), replace(child(frame), label=label)]
                self.assertFalse(policy.observe(frame, rows, LINE, 1000, 800)[1])

    def test_mature_child_or_already_counted_child_is_not_retired(self):
        for changes in ({"class_hits": 7}, {"last_count_frame": 8}, {"guard_pending": True}):
            policy = TwoWheelFragmentOwnership()
            seed(policy)
            self.assertFalse(certify(policy, lambda item: replace(item, **changes))[1])

    def test_owner_must_have_recent_count_and_no_pending_guard(self):
        for changes in ({"class_hits": 7}, {"last_count_frame": None}, {"last_count_frame": -100},
                        {"last_count_frame": 11}, {"guard_pending": True}, {"canonical_id": None}):
            policy = TwoWheelFragmentOwnership()
            seed(policy)
            for frame in range(8, 11):
                self.assertFalse(policy.observe(frame, [replace(owner(frame), **changes), child(frame)], LINE, 1000, 800)[1])

    def test_four_wheel_or_adjacent_full_vehicle_is_not_a_fragment(self):
        for changes in ({"label": "car"}, {"rect": (130., 350., 225., 540.)},
                        {"rect": (210., 350., 250., 410.)}):
            policy = TwoWheelFragmentOwnership()
            seed(policy)
            self.assertFalse(certify(policy, lambda item: replace(item, **changes))[1])

    def test_malformed_proof_types_are_fail_closed(self):
        for changes in ({"label": []}, {"label": {}}, {"canonical_id": True},
                        {"last_count_frame": True}, {"class_hits": True},
                        {"rect": (130., 380., float("nan"), 440.)}):
            policy = TwoWheelFragmentOwnership()
            seed(policy)
            self.assertFalse(certify(policy, lambda item: replace(item, **changes))[1])

    def test_stationary_owner_and_short_owner_history_do_not_certify(self):
        for stationary in (True, False):
            policy = TwoWheelFragmentOwnership()
            if stationary:
                for frame in range(8):
                    policy.observe(frame, [replace(owner(8), last_count_frame=3)], LINE, 1000, 800)
            for frame in range(8, 11):
                parent = replace(owner(8), last_count_frame=3) if stationary else owner(frame)
                self.assertFalse(policy.observe(frame, [parent, child(frame)], LINE, 1000, 800)[1])

    def test_two_equally_nested_owners_are_ambiguous(self):
        policy = TwoWheelFragmentOwnership()
        for frame in range(11):
            rows = [owner(frame), replace(owner(frame), raw_id=11, canonical_id=11)]
            if frame >= 8:
                rows.append(child(frame))
            self.assertFalse(policy.observe(frame, rows, LINE, 1000, 800)[1])

    def test_relative_motion_of_an_independent_rider_breaks_correspondence(self):
        policy = TwoWheelFragmentOwnership()
        seed(policy)
        for frame in range(8, 11):
            item = child(frame)
            rect = tuple(v + (frame - 8) * 10 if i in (0, 2) else v for i, v in enumerate(item.rect))
            self.assertFalse(policy.observe(frame, [owner(frame), replace(item, rect=rect)], LINE, 1000, 800)[1])

    def test_quarantine_is_explicit_and_ambiguous_rows_stay_filtered(self):
        policy = TwoWheelFragmentOwnership()
        seed(policy)
        certify(policy)
        policy.activate(20, 10, 10)
        for frame, rows in ((11, [owner(11), child(11)]),
                            (12, [child(12), replace(child(12), label="car")]),
                            (12, [child(12)])):
            filtered, proofs, _ = policy.observe(frame, rows, LINE, 1000, 800)
            self.assertEqual(filtered, {20})
            self.assertFalse(proofs)
        self.assertEqual(policy.retirements, 1)

    def test_three_separated_whole_boxes_away_from_finite_gate_rearm(self):
        policy = TwoWheelFragmentOwnership()
        policy.activate(20, 10, 10)
        independent = replace(child(11), rect=(700., 600., 740., 660.))
        for frame in (11, 12):
            self.assertEqual(policy.observe(frame, [independent], LINE, 1000, 800)[0], {20})
        filtered, proofs, releases = policy.observe(13, [independent], LINE, 1000, 800)
        self.assertFalse(filtered)
        self.assertFalse(proofs)
        self.assertEqual(releases[0]["reason"], "independent_box_rearm")
        self.assertEqual(policy.releases, 1)

    def test_current_class_wobble_does_not_escape_quarantine_or_fake_absence(self):
        policy = TwoWheelFragmentOwnership()
        policy.activate(20, 10, 10)
        for frame in range(11, 60):
            label = "car" if frame % 2 else "motorcycle"
            rows = [owner(frame), replace(child(frame), label=label)]
            filtered, proofs, releases = policy.observe(frame, rows, LINE, 1000, 800)
            self.assertEqual(filtered, {20})
            self.assertFalse(proofs)
            self.assertFalse(releases)

    def test_other_family_independent_return_can_rearm_with_clear_geometry(self):
        policy = TwoWheelFragmentOwnership()
        policy.activate(20, 10, 10)
        independent = replace(child(11), label="car", rect=(700., 600., 740., 660.))
        for frame in (11, 12):
            self.assertEqual(policy.observe(frame, [independent], LINE, 1000, 800)[0], {20})
        self.assertFalse(policy.observe(13, [independent], LINE, 1000, 800)[0])

    def test_a_box_straddling_gate_or_one_near_corner_cannot_rearm(self):
        for rect in ((700., 190., 740., 250.), (700., 201., 740., 261.)):
            policy = TwoWheelFragmentOwnership()
            policy.activate(20, 10, 10)
            for frame in range(11, 16):
                self.assertEqual(policy.observe(frame, [replace(child(frame), rect=rect)], LINE, 1000, 800)[0], {20})

    def test_long_box_edge_near_finite_gate_cannot_rearm_despite_far_corners(self):
        policy = TwoWheelFragmentOwnership()
        policy.activate(20, 10, 10)
        line = ((450., 500.), (550., 500.))
        for frame in range(11, 16):
            item = replace(child(frame), rect=(200., 430., 800., 490.))
            self.assertEqual(policy.observe(frame, [item], line, 1000, 1000)[0], {20})

    def test_absence_rearm_expires_quarantine_and_bounded_history(self):
        policy = TwoWheelFragmentOwnership()
        seed(policy)
        policy.activate(20, 10, 10)
        self.assertFalse(policy.observe(40, [], LINE, 1000, 800)[2])
        self.assertEqual(policy.observe(41, [], LINE, 1000, 800)[2][0]["reason"], "absence_rearm")
        policy.observe(100, [], LINE, 1000, 800)
        self.assertFalse(policy._history)
        self.assertFalse(policy._first)
        self.assertFalse(policy._pairs)


class UncommittedDiscardTests(unittest.TestCase):
    def test_forced_fresh_detaches_existing_raw_alias_without_changing_owner(self):
        resolver = TrackContinuityResolver()
        resolver.resolve(10, (100., 100.), "motorcycle", 9, 1000, 800, rect=(80., 80., 120., 120.))
        resolver.alias_raw_id(20, 10)
        self.assertEqual(resolver.lineage_size(10), 2)
        old_velocity = resolver.velocity_for(10)
        resolver.require_fresh_identity_for_raw(20)
        fresh, stitched = resolver.resolve(20, (102., 102.), "motorcycle", 10, 1000, 800, rect=(82., 82., 122., 122.))
        self.assertLess(fresh, 0)
        self.assertFalse(stitched)
        self.assertEqual(resolver._canonical_raw_ids[10], {10})
        self.assertEqual(resolver.canonical_for_raw(10), 10)
        self.assertEqual(resolver.velocity_for(10), old_velocity)

    def test_rearmed_synthetic_child_does_not_reuse_expired_positive_semantic_key(self):
        resolver = TrackContinuityResolver()
        resolver.resolve(20, (50., 50.), "motorcycle", 1, 1000, 800, rect=(40., 40., 60., 60.))
        child_id, _ = resolver.resolve(20, (500., 500.), "motorcycle", 2, 1000, 800,
                                       {20}, rect=(490., 490., 510., 510.))
        self.assertLess(child_id, 0)
        self.assertTrue(resolver.discard_fragment_identity(20, child_id))
        resolver._cleanup(10000)
        resolver.require_fresh_identity_for_raw(20)
        fresh, stitched = resolver.resolve(20, (50., 150.), "motorcycle", 10001, 1000, 800,
                                          rect=(40., 140., 60., 160.))
        self.assertLess(fresh, 0)
        self.assertNotEqual(fresh, child_id)
        self.assertFalse(stitched)

    def test_release_requires_fresh_identity_even_next_to_a_tempting_counted_owner(self):
        resolver = TrackContinuityResolver()
        resolver.resolve(20, (50., 50.), "motorcycle", 1, 1000, 800, rect=(40., 40., 60., 60.))
        resolver.discard_fragment_identity(20, 20)
        resolver.resolve(10, (100., 100.), "motorcycle", 9, 1000, 800, rect=(80., 80., 120., 120.))
        resolver.require_fresh_identity_for_raw(20)
        fresh, stitched = resolver.resolve(20, (102., 102.), "motorcycle", 10, 1000, 800, rect=(82., 82., 122., 122.))
        self.assertNotIn(fresh, (10, 20))
        self.assertFalse(stitched)
        self.assertEqual(resolver.lineage_size(fresh), 1)
        self.assertEqual(resolver.velocity_for(fresh), (0., 0.))
        self.assertEqual(resolver.canonical_for_raw(10), 10)

    def test_retired_canonical_is_reserved_across_ttl_for_fresh_return(self):
        resolver = TrackContinuityResolver()
        self.assertEqual(resolver.resolve(20, (50., 50.), "motorcycle", 1, 1000, 800, rect=(40., 40., 60., 60.))[0], 20)
        self.assertTrue(resolver.discard_fragment_identity(20, 20))
        self.assertIsNone(resolver.canonical_for_raw(20))
        resolver._cleanup(10000)
        fresh, stitched = resolver.resolve(20, (50., 150.), "motorcycle", 10001, 1000, 800, rect=(40., 140., 60., 160.))
        self.assertNotEqual(fresh, 20)
        self.assertFalse(stitched)
        self.assertEqual(resolver.lineage_size(fresh), 1)

    def test_alias_lineage_cannot_be_discarded_as_one_fragment(self):
        resolver = TrackContinuityResolver()
        resolver.resolve(10, (50., 50.), "motorcycle", 1, 1000, 800, rect=(40., 40., 60., 60.))
        resolver.alias_raw_id(20, 10)
        self.assertFalse(resolver.discard_fragment_identity(20, 10))
        self.assertEqual(resolver.canonical_for_raw(10), 10)
        self.assertEqual(resolver.canonical_for_raw(20), 10)

    def test_all_uncommitted_gate_histories_can_be_discarded_without_count_change(self):
        line = CountingLine(0., .5, 1., .5)
        gates = [LineCrossingCounter(line), VerifiedAnchorSpanRescuer(line),
                 TwoWheelCenterCrossingRescuer(line), HeavyVehicleCrossingRescuer(line)]
        for gate in gates:
            gate.update(20, (500., 300.), 1000, 800, 1)
            self.assertTrue(gate.can_discard_uncommitted_track(20))
            self.assertTrue(gate.discard_uncommitted_track(20))
            self.assertNotIn(20, gate._tracks)
        self.assertEqual((gates[0].in_count, gates[0].out_count), (0, 0))
        self.assertIsNone(gates[1].finalize_lost(20, 2))

    def test_accepted_primary_passage_cannot_be_erased(self):
        gate = LineCrossingCounter(CountingLine(0., .5, 1., .5))
        gate.update(20, (500., 300.), 1000, 800, 1)
        self.assertEqual(gate.update(20, (500., 500.), 1000, 800, 2), "in")
        self.assertFalse(gate.can_discard_uncommitted_track(20))
        self.assertFalse(gate.discard_uncommitted_track(20))
        self.assertEqual(gate.accepted_passage_frame_for(20), 2)
        self.assertEqual(gate.in_count, 1)

    def test_accepted_secondary_passages_cannot_be_erased(self):
        line = CountingLine(0., .5, 1., .5)
        for gate in (VerifiedAnchorSpanRescuer(line), TwoWheelCenterCrossingRescuer(line), HeavyVehicleCrossingRescuer(line)):
            gate.mark_counted(20, "in", 2)
            self.assertFalse(gate.can_discard_uncommitted_track(20))
            self.assertFalse(gate.discard_uncommitted_track(20))


if __name__ == "__main__":
    unittest.main()
