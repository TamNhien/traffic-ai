"""Actual pure route helpers; no HTTP, database, or model substitutes."""
import ast
import copy
from pathlib import Path
from types import SimpleNamespace


def _helpers():
    path = Path(__file__).parents[1] / "app/api/routes.py"
    tree = ast.parse(path.read_text())
    names = {"_benchmark_trace_targets", "_observed_benchmark_trace_targets", "_scope_crossing_trace_audit",
             "_scope_observed_track_audit", "_attach_benchmark_trace_diagnosis"}
    body = [ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)]
    body.extend(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names)
    namespace = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])), str(path), "exec"), namespace)
    return namespace


def _audit():
    return {"schema_version": 1, "scope": "canonical_track_window", "tracking_id": 77,
            "identity_proven": False, "status": "observed", "reason": "recorded_rectangles",
            "target": {"frames": 2, "first_frame": 10, "last_frame": 11, "first_time": 1., "last_time": 1.04,
                       "raw_track_ids": [70], "rect_motion": {"dx": 1., "dy": -2., "gap_frames": 1, "pixels_per_frame": [1., -2.]},
                       "filtered_velocity": [3., 4.]},
            "peers": [{"tracking_id": 88, "identity_proven": False, "co_visible_frames": 2,
                       "nested_frames": 2, "max_consecutive_frames": 2, "first_frame": 10, "last_frame": 11,
                       "first_time": 1., "last_time": 1.04, "containment_min": .95, "containment_max": .99,
                       "bottom_alignment_min": .01, "bottom_alignment_max": .02, "raw_track_ids": [80],
                       "target_rect_motion": None, "peer_rect_motion": None,
                       "target_filtered_velocity": [3., 4.], "peer_filtered_velocity": [1., 2.]}],
            "raw_id_handoffs": [], "records_limit": 4, "truncated": False,
            "conflicting_frames": 0, "out_of_order_frames": 0}


def test_v0597_fp_and_direction_targets_use_persisted_canonical_source_clock():
    report = {"missed_items": [], "class_mismatch_items": [],
              "false_positive_items": [{"ai_event_id": 11, "time": 999., "tracking_id": 999, "near_matched_ai_event_id": 12}],
              "direction_mismatch_items": [{"ai_event_id": 13, "time": 777., "tracking_id": 777}]}
    events = [SimpleNamespace(id=11, tracking_id=77, source_time_seconds=1.03125),
              SimpleNamespace(id=12, tracking_id=88, source_time_seconds=1.25),
              SimpleNamespace(id=13, tracking_id=99, source_time_seconds=2.12345)]
    targets = _helpers()["_benchmark_trace_targets"](report, events)
    assert [time for _, time in targets] == [1.03125, 2.12345]
    assert [item["ai_tracking_id"] for item, _ in targets] == [77, 99]
    assert targets[0][0]["near_matched_tracking_id"] == 88
    assert report["false_positive_items"][0]["time"] == 999.


def test_v0597_missing_or_malformed_event_cannot_authorize_observed_owner():
    fn = _helpers()["_observed_benchmark_trace_targets"]
    for clock, tid in [(float("nan"), 77), (10**1000, 77), (1., True), (True, 77), (1., 10**1000)]:
        report = {"false_positive_items": [{"ai_event_id": 11, "time": 1., "tracking_id": 77}]}
        assert fn(report, {11: SimpleNamespace(tracking_id=tid, source_time_seconds=clock)}) == []
        assert "ai_tracking_id" not in report["false_positive_items"][0]
    assert fn({"false_positive_items": [{"ai_event_id": 11, "time": 1., "tracking_id": 77}]}, {}) == []


def test_v0597_owner_scope_and_identity_claim_are_validated_before_attach():
    helper = _helpers()["_scope_observed_track_audit"]
    for change in [{"tracking_id": 88}, {"tracking_id": True}, {"identity_proven": True}, {"scope": "nearby_tracks"}]:
        assert helper({**_audit(), **change}, 77) is None
    assert helper(_audit(), None) is None
    assert helper(_audit(), 77)["target"]["raw_track_ids"] == [70]


def test_v0597_scoper_whitelists_numeric_evidence_and_bounds_arrays():
    audit = _audit()
    audit["private_path"] = "/private"
    audit["target"]["password"] = "secret"
    audit["target"]["filtered_velocity"] = [float("nan"), 0]
    audit["peers"] = audit["peers"] * 20
    before = copy.deepcopy(audit)
    result = _helpers()["_scope_observed_track_audit"](audit, 77)
    assert "private_path" not in result and "password" not in result["target"]
    assert result["target"]["filtered_velocity"] is None
    assert len(result["peers"]) == 4 and result["truncated"] is True
    assert len(audit["peers"]) == len(before["peers"]) == 20


def test_v0597_unavailable_or_conflicting_audit_cannot_retain_pair_or_handoff():
    helper = _helpers()["_scope_observed_track_audit"]
    for change in [{"status": "unavailable"}, {"conflicting_frames": 1}]:
        result = helper({**_audit(), **change}, 77)
        assert result["status"] == "unavailable" and result["target"] is None
        assert result["peers"] == result["raw_id_handoffs"] == []


def test_v0597_attach_scopes_new_audit_without_rewriting_report_or_input():
    item = {"ai_tracking_id": 77, "ai_event_id": 11, "time": 1., "direction": "out", "vehicle_type": "motorcycle"}
    diagnosis = {"reason": "crossing_delivery_observed", "observed_track_audit": _audit()}
    before = copy.deepcopy(diagnosis)
    _helpers()["_attach_benchmark_trace_diagnosis"](item, diagnosis)
    assert item["direction"] == "out" and item["vehicle_type"] == "motorcycle" and item["time"] == 1.
    assert item["diagnosis"]["observed_track_audit"]["tracking_id"] == 77
    assert diagnosis == before
    other = {"ai_tracking_id": 99}
    _helpers()["_attach_benchmark_trace_diagnosis"](other, diagnosis)
    assert "observed_track_audit" not in other["diagnosis"]
