"""Pure policy checks; runnable without inference or web dependencies using -S."""
import copy
import unittest

from app.classification import (
    contextual_bicycle_decision,
    contextual_bicycle_repeated_target_decision,
)


class RepeatedTargetContextTests(unittest.TestCase):
    def setUp(self):
        self.wide = [(13345, "general", .462890625, 0.0),
                     (13355, "general", .70068359375, 0.0)]
        self.tight = {"general": (13355, "bicycle", .303955078125)}
        self.kwargs = {"frame_index": 13355, "detector_confidence": .638671875}

    def decide(self, wide=None, tight=None, **kwargs):
        return contextual_bicycle_repeated_target_decision(
            self.wide if wide is None else wide,
            self.tight if tight is None else tight,
            **(self.kwargs | kwargs),
        )

    def test_recorded_three_view_evidence_returns_current_score_without_fusion(self):
        self.assertIsNone(contextual_bicycle_decision([("general", .70068359375)]))
        decision, audit = self.decide()
        self.assertEqual(decision, ("bicycle", .70068359375))
        self.assertEqual(audit["source"], "general")
        self.assertEqual(audit["previous_wide_frame"], 13345)
        self.assertFalse(audit["same_model_probability_fusion"])
        self.assertFalse(audit["physical_identity_proven"])

    def test_current_wide_must_beat_primary_motorcycle(self):
        for primary in (.99, .70, .70068359375 - .014):
            with self.subTest(primary=primary):
                self.assertIsNone(self.decide(detector_confidence=primary)[0])

    def test_invalid_primary_is_fail_closed(self):
        for primary in (None, True, -.01, 1.01, float("nan"), float("inf")):
            with self.subTest(primary=primary):
                self.assertIsNone(self.decide(detector_confidence=primary)[0])
        with self.assertRaises(TypeError):
            contextual_bicycle_repeated_target_decision(self.wide, self.tight, frame_index=13355)

    def test_tight_current_and_prior_wide_must_be_same_source(self):
        for tight in ({}, {"domain": (13355, "bicycle", .9)},
                      {"general": (13354, "bicycle", .9)}):
            with self.subTest(tight=tight):
                self.assertIsNone(self.decide(tight=tight)[0])
        self.assertIsNone(self.decide(wide=[(13345, "domain", .8, 0), self.wide[1]])[0])

    def test_prior_must_be_distinct_frame_and_inside_history(self):
        for wide in ([self.wide[1]], [self.wide[1], self.wide[1]],
                     [(13336, "general", .9, 0), self.wide[1]],
                     [(13355, "domain", .9, 0), self.wide[1]]):
            with self.subTest(wide=wide):
                self.assertIsNone(self.decide(wide=wide)[0])
        self.assertIsNotNone(self.decide(wide=[(13337, "general", .4, 0), self.wide[1]])[0])

    def test_repeating_identical_observations_does_not_inflate_confidence(self):
        decision, _ = self.decide(wide=self.wide * 5)
        self.assertEqual(decision, ("bicycle", .70068359375))

    def test_conflicting_same_frame_source_observations_reject(self):
        decision, audit = self.decide(wide=self.wide + [(13345, "general", .9, 0)])
        self.assertIsNone(decision)
        self.assertEqual(audit["reason"], "conflicting_wide_observations")

    def test_future_context_or_tight_is_never_current_evidence(self):
        self.assertIsNone(self.decide(wide=self.wide + [(13356, "general", .9, 0)])[0])
        self.assertIsNone(self.decide(tight={"general": (13356, "bicycle", .9)})[0])

    def test_every_recent_wide_source_can_veto(self):
        for frame, source in ((13345, "general"), (13350, "domain"), (13355, "domain")):
            with self.subTest(frame=frame, source=source):
                wide = [row for row in self.wide if row[:2] != (frame, source)]
                self.assertIsNone(self.decide(wide=wide + [(frame, source, .1, .8)])[0])
        self.assertIsNotNone(self.decide(wide=self.wide + [(13336, "domain", 0, .9)])[0])

    def test_current_tight_motorcycle_from_any_source_can_veto(self):
        for source in ("domain", "general"):
            with self.subTest(source=source):
                tight = self.tight | {source: (13355, "motorcycle", .11)}
                self.assertIsNone(self.decide(tight=tight)[0])
        self.assertIsNotNone(self.decide(tight=self.tight | {"domain": (13355, "motorcycle", .10)})[0])

    def test_each_existing_threshold_is_required(self):
        for wide, tight in (
            ([(13345, "general", .339, 0), self.wide[1]], self.tight),
            ([self.wide[0], (13355, "general", .579, 0)], self.tight),
            (self.wide, {"general": (13355, "bicycle", .179)}),
            ([(13345, "general", .4, .39), self.wide[1]], self.tight),
            ([self.wide[0], (13355, "general", .7, .69)], self.tight),
        ):
            with self.subTest(wide=wide, tight=tight):
                self.assertIsNone(self.decide(wide=wide, tight=tight)[0])

    def test_nonfinite_or_out_of_range_evidence_rejects(self):
        for confidence in (True, -.1, 1.1, float("nan"), float("inf")):
            with self.subTest(confidence=confidence):
                self.assertIsNone(self.decide(wide=[self.wide[0], (13355, "general", confidence, 0)])[0])
                self.assertIsNone(self.decide(tight={"general": (13355, "bicycle", confidence)})[0])

    def test_invalid_frame_and_configuration_reject(self):
        for key, value in (("frame_index", True), ("frame_index", -1), ("history_frames", 0),
                           ("history_frames", 18.0), ("tight_confidence", float("nan")),
                           ("min_source_win", float("inf")), ("motorcycle_veto", -.1)):
            with self.subTest(key=key, value=value):
                self.assertIsNone(self.decide(**{key: value})[0])

    def test_malformed_tight_labels_are_fail_closed(self):
        for label in (None, [], {}, "pedestrian"):
            with self.subTest(label=label):
                self.assertIsNone(self.decide(tight={"general": (13355, label, .9)})[0])

    def test_inputs_are_not_consumed_or_mutated(self):
        original = copy.deepcopy((self.wide, self.tight))
        self.decide()
        self.assertEqual((self.wide, self.tight), original)


if __name__ == "__main__":
    unittest.main()
