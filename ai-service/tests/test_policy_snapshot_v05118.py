"""Portable regression checks for effective, sanitized policy metadata."""
from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace
import unittest

from app.counting import (
    CountingLine, LineCrossingCounter, VerifiedAnchorSpanRescuer,
    HeavyVehicleCrossingRescuer, TwoWheelCenterCrossingRescuer,
)
from app.policy_snapshot import capture_policy_snapshot, POLICY_FIELDS
from app.tracking import TrackContinuityResolver


def _components():
    defaults = {"bool": False, "int": 2, "number": 0.25, "roi": "full"}
    result = {
        name: SimpleNamespace(**{field: defaults[kind] for field, kind in fields})
        for name, fields in POLICY_FIELDS.items()
    }
    line = CountingLine()
    result.update({
        "resolver": TrackContinuityResolver(),
        "primary": LineCrossingCounter(line),
        "anchor_span": VerifiedAnchorSpanRescuer(line),
        "heavy_center": HeavyVehicleCrossingRescuer(line),
        "two_wheel_center": TwoWheelCenterCrossingRescuer(line),
    })
    return result


class PolicySnapshotTests(unittest.TestCase):
    def test_records_constructed_clamped_parameters(self):
        components = _components()
        components["primary"] = LineCrossingCounter(
            CountingLine(), history_gap_frames=-3, interpolation_gap_frames=999,
            rescue_min_normal_ratio=8.0, passage_rearm_min_frames=-8,
        )
        components["resolver"] = TrackContinuityResolver(max_gap_frames=-5, max_distance_ratio=-1.0)
        result = capture_policy_snapshot(components)
        self.assertEqual(result["capture_status"], "complete")
        primary = result["configuration"]["primary"]
        self.assertEqual(primary["history_gap_frames"], 2)
        self.assertEqual(primary["interpolation_gap_frames"], 2)
        self.assertEqual(primary["rescue_min_normal_ratio"], 1.0)
        self.assertEqual(primary["passage_rearm_min_frames"], 1)
        self.assertEqual(result["configuration"]["resolver"]["max_distance_ratio"], 0.01)

    def test_digest_changes_when_effective_parameter_changes(self):
        components = _components()
        before = capture_policy_snapshot(components)
        components["primary"].rescue_min_normal_ratio = 0.731
        after = capture_policy_snapshot(components)
        self.assertNotEqual(before["configuration_sha256"], after["configuration_sha256"])

    def test_digest_is_canonical_and_input_mapping_order_independent(self):
        components = _components()
        result = capture_policy_snapshot(components)
        reversed_result = capture_policy_snapshot(dict(reversed(list(components.items()))))
        self.assertEqual(result, reversed_result)
        body = {key: value for key, value in result.items() if key != "configuration_sha256"}
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
        self.assertEqual(result["configuration_sha256"], hashlib.sha256(encoded.encode()).hexdigest())
        self.assertEqual(result["digest_scope"], "allowlisted_effective_algorithm_parameters")

    def test_counter_geometry_and_private_path_changes_do_not_change_scoped_digest(self):
        components = _components()
        before = capture_policy_snapshot(components)
        components["primary"].in_count = 999
        components["primary"].line = CountingLine(0.1, 0.3, 0.9, 0.4)
        components["worker"].shared_token = "secret-do-not-log"
        components["worker"].model_name = "/private/model.pt"
        components["worker"].backend_url = "https://private.invalid/token"
        components["worker"].source_fps = 1000.0
        result = capture_policy_snapshot(components)
        self.assertEqual(before, result)
        self.assertNotIn("secret-do-not-log", json.dumps(result))
        self.assertNotIn("/private/", json.dumps(result))

    def test_never_enumerates_or_accesses_unlisted_attributes(self):
        class Restricted:
            def __getattribute__(self, name):
                if name == "confidence_threshold":
                    return 0.17
                raise AssertionError("unlisted secret accessed")
        components = _components()
        components["detector"] = Restricted()
        self.assertEqual(capture_policy_snapshot(components)["capture_status"], "complete")

    def test_optional_absence_is_distinct_from_present_disabled(self):
        components = _components()
        components["anchor_span"].enabled = False
        disabled = capture_policy_snapshot(components)
        components["anchor_span"] = None
        absent = capture_policy_snapshot(components)
        self.assertEqual(disabled["configuration"]["anchor_span"]["enabled"], False)
        self.assertEqual(absent["component_presence"]["anchor_span"], "absent")
        self.assertNotIn("anchor_span", absent["configuration"])
        self.assertEqual(absent["capture_status"], "complete")
        self.assertNotEqual(disabled["configuration_sha256"], absent["configuration_sha256"])

    def test_missing_required_component_and_missing_field_are_partial(self):
        components = _components()
        components["primary"] = None
        del components["worker"].iou
        result = capture_policy_snapshot(components)
        self.assertEqual(result["capture_status"], "partial")
        self.assertEqual(result["component_presence"]["primary"], "absent")
        self.assertEqual(result["missing_fields"], ["worker.iou"])
        self.assertNotIn("iou", result["configuration"]["worker"])

    def test_new_endpoint_guard_records_actual_boolean_and_missing_is_unknown(self):
        components = _components()
        components["worker"]._endpoint_rescue_guard_enabled = True
        enabled = capture_policy_snapshot(components)
        self.assertIs(enabled["configuration"]["worker"]["_endpoint_rescue_guard_enabled"], True)
        del components["worker"]._endpoint_rescue_guard_enabled
        unknown = capture_policy_snapshot(components)
        self.assertEqual(unknown["capture_status"], "partial")
        self.assertIn("worker._endpoint_rescue_guard_enabled", unknown["missing_fields"])
        self.assertNotIn("_endpoint_rescue_guard_enabled", unknown["configuration"]["worker"])

    def test_rejects_nonfinite_numbers_bool_as_int_and_string_numbers(self):
        components = _components()
        components["worker"].iou = float("nan")
        components["worker"].refine_max_lag = float("inf")
        components["worker"].imgsz = True
        components["worker"].hybrid_mode = 0
        components["detector"].confidence_threshold = "0.06"
        result = capture_policy_snapshot(components)
        self.assertEqual(result["capture_status"], "partial")
        self.assertEqual(set(result["invalid_fields"]), {
            "worker.iou", "worker.refine_max_lag", "worker.imgsz", "worker.hybrid_mode",
            "detector.confidence_threshold",
        })
        json.dumps(result, allow_nan=False)

    def test_getter_failures_and_invalid_objects_never_expose_exception_or_repr(self):
        class Dangerous:
            @property
            def confidence_threshold(self):
                raise RuntimeError("credential-in-exception")
        components = _components()
        components["detector"] = Dangerous()
        result = capture_policy_snapshot(components)
        self.assertEqual(result["unreadable_fields"], ["detector.confidence_threshold"])
        self.assertNotIn("credential", json.dumps(result))
        class Secret:
            def __repr__(self):
                raise AssertionError("must not format secret")
        components["detector"] = SimpleNamespace(confidence_threshold=Secret())
        result = capture_policy_snapshot(components)
        self.assertEqual(result["invalid_fields"], ["detector.confidence_threshold"])

    def test_roi_is_a_closed_enum(self):
        components = _components()
        components["worker"].detection_roi_mode = "https://private.invalid/credential"
        result = capture_policy_snapshot(components)
        self.assertEqual(result["invalid_fields"], ["worker.detection_roi_mode"])
        self.assertNotIn("private.invalid", json.dumps(result))

    def test_capture_is_read_only_and_rejects_nonmapping_input(self):
        components = _components()
        worker_before = dict(vars(components["worker"]))
        result = capture_policy_snapshot(components)
        self.assertEqual(vars(components["worker"]), worker_before)
        self.assertEqual(capture_policy_snapshot(components), result)
        with self.assertRaises(TypeError):
            capture_policy_snapshot([])


if __name__ == "__main__":
    unittest.main()
