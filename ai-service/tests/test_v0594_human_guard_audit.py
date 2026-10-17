"""Audit evidence is source-bound and cannot authorize or reject a crossing."""
import copy
import json
from types import SimpleNamespace

from app import benchmark_trace
from app.human_guard import HumanGuardDecision, HumanGuardTrackPolicy, human_guard_decision_audit
from app.worker import PipelineWorker


def _worker(decision=None):
    worker = PipelineWorker.__new__(PipelineWorker)
    worker._human_guard_policy = HumanGuardTrackPolicy(required_strikes=2)
    worker._human_guard_last_check = {}
    worker._human_guard_last_observation = {}
    worker._human_rider_tracks_seen = set()
    worker._human_guard_model = object()
    worker._human_guard_ids = [0, 3]
    worker.human_guard_check_interval = 8
    worker.state = SimpleNamespace(human_guard_rejections=0, rider_guard_rescues=0, human_guard_checks=0)
    worker.calls = []

    def verify(*args, **kwargs):
        worker.calls.append((args, kwargs))
        return decision

    worker._verify_human_candidate = verify
    return worker


def _observe(worker, frame, *, force=False):
    return worker._observe_human_guard(7, frame, None, (0, 0, 20, 40), "motorcycle", .4,
                                       "cpu", False, force=force)


def _audit(worker, frame, *, label="motorcycle"):
    rows = [{"track_id": 7, "label": label}]
    assert worker._human_guard_trace_tracks(rows, frame) is rows
    return rows[0]["human_guard_decision_audit"]


def _reject():
    return HumanGuardDecision(True, "person_dominates_two_wheel", .82, .03, .02, .91, .96,
                              hard_reject=True)


def _write_trace(tmp_path, monkeypatch, rows):
    monkeypatch.setattr(benchmark_trace, "TRACE_ROOT", tmp_path)
    benchmark_trace.trace_path(3).write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _row(audit, *, time=4.0):
    return {"frame_index": audit["frame_index"], "source_time_seconds": time,
            "detections": 1, "tracks": 1, "road_tracks": 1,
            "gate_tracks": [{"track_id": audit["track_id"], "label": "motorcycle",
                              "anchor_signed": -.01, "center_signed": -.02,
                              "human_guard_decision_audit": audit}]}


def test_v0594_guard_audit_distinct_frames_and_same_frame_cache_preserve_strikes():
    worker = _worker(_reject())
    assert _observe(worker, 100)[0] == "pending"
    first = _audit(worker, 100)
    assert first["context"] == "fresh" and first["strikes"] == 1
    assert _observe(worker, 100, force=True)[0] == "pending"
    cached = _audit(worker, 100)
    assert cached["context"] == "same_frame_cache" and cached["forced"] is True
    assert cached["decision_frame_index"] == 100 and cached["decision_age_frames"] == 0
    assert cached["strikes"] == 1 and len(worker.calls) == 1
    assert _observe(worker, 101, force=True)[0] == "rejected"
    assert worker.state.human_guard_rejections == 1
    assert _audit(worker, 101)["strikes"] == 2


def test_v0594_guard_audit_interval_reuse_names_original_decision_clock():
    worker = _worker(_reject())
    _observe(worker, 100)
    assert _observe(worker, 104) == ("pending", None)
    audit = _audit(worker, 104)
    assert audit["context"] == "interval_cache"
    assert audit["frame_index"] == 104 and audit["last_check_frame_index"] == 100
    assert audit["decision_frame_index"] == 100 and audit["decision_age_frames"] == 4
    assert audit["decision"]["person_confidence"] == .82
    assert audit["strikes"] == 1 and len(worker.calls) == 1


def test_v0594_guard_audit_out_of_order_never_relabels_future_evidence_as_current():
    worker = _worker(_reject())
    _observe(worker, 100)
    assert _observe(worker, 99, force=True) == ("pending", None)
    audit = _audit(worker, 99)
    assert audit["context"] == "out_of_order" and audit["decision_frame_index"] == 100
    assert audit["decision_age_frames"] is None
    assert worker._human_guard_last_check[7] == 100 and len(worker.calls) == 1


def test_v0594_guard_audit_unavailable_has_null_opinion_and_preserves_rejected_policy():
    worker = _worker()
    worker._human_guard_model = None
    worker._human_guard_policy.observe(7, _reject(), frame_index=90)
    worker._human_guard_policy.observe(7, _reject(), frame_index=91)
    assert _observe(worker, 100, force=True) == ("rejected", None)
    audit = _audit(worker, 100)
    assert audit["context"] == "guard_unavailable" and audit["policy_status"] == "rejected"
    assert audit["last_check_frame_index"] == 100
    assert audit["decision"] is None and audit["decision_frame_index"] is None
    assert audit["decision_age_frames"] is None and audit["strikes"] == 2
    assert worker.state.human_guard_rejections == 0


def test_v0594_guard_audit_no_result_and_not_requested_are_distinct():
    worker = _worker()
    _observe(worker, 100)
    assert _audit(worker, 100)["context"] == "no_decision"
    skipped = _audit(worker, 101)
    assert skipped["context"] == "not_requested" and skipped["decision"] is None
    rows = [{"track_id": 8, "label": "car"}, {"track_id": 7, "label": "car"}]
    worker._human_guard_trace_tracks(rows, 101)
    assert "human_guard_decision_audit" not in rows[0]
    assert rows[1]["human_guard_decision_audit"]["context"] == "not_requested"


def test_v0594_guard_audit_rider_release_keeps_original_policy_action():
    worker = _worker(HumanGuardDecision(False, "rider_evidence", .8, .4, .3,
                                       .9, .9, rider_supported=True))
    worker._human_guard_policy.observe(7, _reject(), frame_index=90)
    worker._human_guard_policy.observe(7, _reject(), frame_index=91)
    assert _observe(worker, 100)[0] == "released"
    audit = _audit(worker, 100)
    assert audit["policy_status"] == "rider" and audit["policy_action"] == "released"
    assert audit["strikes"] == 0 and audit["last_strike_frame_index"] is None
    assert worker.state.rider_guard_rescues == 1


def test_v0594_guard_audit_trace_failures_do_not_change_guard_policy(monkeypatch):
    from app import worker as worker_module
    worker = _worker(_reject())

    def fail(*_args, **_kwargs):
        raise RuntimeError("diagnostic-only failure")

    monkeypatch.setattr(worker_module, "human_guard_decision_audit", fail)
    assert _observe(worker, 100)[0] == "pending"
    rows = [{"track_id": 7, "label": "motorcycle"}]
    assert worker._human_guard_trace_tracks(rows, 100) == [{"track_id": 7, "label": "motorcycle"}]
    assert _observe(worker, 101, force=True)[0] == "rejected"
    assert worker._human_guard_policy.strikes[7] == 2 and worker.state.human_guard_rejections == 1


def test_v0594_guard_audit_is_finite_whitelisted_and_bounded_per_frame():
    worker = _worker(_reject())
    decision = _reject()
    decision.audit_evidence = {"person_confidence": float("nan"), "vehicle_confidence": float("inf"),
                               "nearby_vehicle_confidence": "private/model.pt", "speed_ratio": -1,
                               "image_path": "private.jpg", "token": "secret"}
    audit = human_guard_decision_audit(7, 100, worker._human_guard_policy, (100, "pending", decision), "fresh")
    encoded = json.dumps(audit, allow_nan=False)
    assert len(encoded) < 1200 and "private" not in encoded and "secret" not in encoded
    assert audit["decision"]["person_confidence"] is None
    assert audit["decision"]["vehicle_confidence"] is None
    assert audit["decision"]["nearby_vehicle_confidence"] is None
    assert audit["decision"]["speed_ratio"] is None
    for tid in range(300):
        worker._record_human_guard_audit_context(tid, 100, "fresh")
    assert len(worker._human_guard_audit_context_this_frame) == 256
    worker._record_human_guard_audit_context(999, 101, "fresh")
    assert worker._human_guard_audit_context_this_frame == {999: ("fresh", False)}


def test_v0594_guard_audit_skipped_geometry_is_unknown_instead_of_zero():
    decision = HumanGuardDecision(False)
    decision.audit_evidence = {"person_detected": True, "target_person_like": False,
                               "person_confidence": .95, "vehicle_confidence": .02,
                               "nearby_vehicle_confidence": .1}
    audit = human_guard_decision_audit(7, 100, HumanGuardTrackPolicy(), (100, "keep", decision), "fresh")
    assert audit["decision"]["person_confidence"] == .95
    assert audit["decision"]["geometry_computed"] is False
    assert audit["decision"]["overlap_iou"] is None and audit["decision"]["target_coverage"] is None


def _verifier_worker():
    import numpy as np
    worker = _worker()
    del worker._verify_human_candidate

    class Tensor:
        def __init__(self, value):
            self.value = value

        def cpu(self):
            return self

        def int(self):
            return self

        def tolist(self):
            return self.value

    boxes = SimpleNamespace(xyxy=Tensor([[30, 16, 90, 56], [30, 16, 90, 56]]),
                            cls=Tensor([0, 3]), conf=Tensor([.95, .12]))
    prediction = SimpleNamespace(boxes=boxes, names={0: "person", 3: "motorcycle"})
    worker._human_guard_model = SimpleNamespace(predict=lambda *_args, **_kwargs: [prediction])
    worker.human_guard_conf, worker.human_guard_imgsz = .08, 512
    return worker, np.zeros((160, 160, 3), dtype=np.uint8)


def test_v0594_guard_actual_verifier_retains_raw_neutral_opinions_without_changing_decision():
    worker, frame = _verifier_worker()
    decision = worker._verify_human_candidate(frame, (30, 30, 90, 70), "motorcycle", .4, "cpu", False)
    assert decision.reject is False and decision.person_confidence == 0
    assert decision.audit_evidence["person_confidence"] == .95
    assert decision.audit_evidence["vehicle_confidence"] == .12
    assert decision.audit_evidence["target_person_like"] is False
    audit = human_guard_decision_audit(7, 100, worker._human_guard_policy, (100, "keep", decision), "fresh")
    assert audit["decision"]["person_confidence"] == .95
    assert audit["decision"]["overlap_iou"] is None
    assert worker.state.human_guard_checks == 1


def test_v0594_guard_actual_verifier_audit_failure_preserves_successful_model_decision(monkeypatch):
    from app import worker as worker_module
    worker, frame = _verifier_worker()

    def fail(*_args, **_kwargs):
        raise RuntimeError("trace opinions unavailable")

    monkeypatch.setattr(worker_module, "is_person_like_two_wheel_box", fail)
    decision = worker._verify_human_candidate(frame, (30, 30, 90, 70), "motorcycle", .4, "cpu", False)
    assert isinstance(decision, HumanGuardDecision) and decision.reject is False
    assert decision.audit_evidence is None and worker.state.human_guard_checks == 1


def test_v0594_guard_diagnosis_preserves_scope_and_omits_private_trace_fields(tmp_path, monkeypatch):
    worker = _worker(_reject())
    _observe(worker, 100)
    audit = _audit(worker, 100)
    audit["image_path"] = "private.jpg"
    audit["decision"]["model_path"] = "private/model.pt"
    other = copy.deepcopy(audit)
    other["track_id"] = 8
    _write_trace(tmp_path, monkeypatch, [_row(other), _row(audit)])
    result = benchmark_trace.diagnose_trace(3, [4, 4], tracking_ids=[7, None])
    matched, nearby = [item["human_guard_audit"] for item in result["items"]]
    assert matched["scope"] == "matched_track" and [row["track_id"] for row in matched["records"]] == [7]
    assert nearby["scope"] == "nearby_time_window" and {row["track_id"] for row in nearby["records"]} == {7, 8}
    assert "private" not in json.dumps(result, allow_nan=False)
    assert result["items"][0]["reason"] != "human_guard_rejected"


def test_v0594_guard_diagnosis_bounds_records_and_rejects_malformed_evidence(tmp_path, monkeypatch):
    worker = _worker(_reject())
    rows = []
    for frame in range(100, 120):
        _observe(worker, frame, force=True)
        rows.append(_row(_audit(worker, frame)))
    malformed = copy.deepcopy(rows[-1])
    malformed["gate_tracks"][0]["human_guard_decision_audit"]["decision"]["person_confidence"] = float("nan")
    rows.append(malformed)
    _write_trace(tmp_path, monkeypatch, rows)
    audit = benchmark_trace.diagnose_trace(3, [4], tracking_ids=[7])["items"][0]["human_guard_audit"]
    assert audit["truncated"] is True and audit["records_limit"] == 8 and len(audit["records"]) == 8
    assert [row["frame_index"] for row in audit["records"]] == list(range(112, 120))
    assert all(row["decision"]["person_confidence"] == .82 for row in audit["records"])
    json.dumps(audit, allow_nan=False)


def test_v0594_guard_diagnosis_older_traces_and_mismatched_clocks_have_no_invented_audit(tmp_path, monkeypatch):
    worker = _worker(_reject())
    _observe(worker, 100)
    valid = _audit(worker, 100)
    invalid = []
    for key, value in (("track_id", 9), ("frame_index", 101), ("schema_version", True),
                       ("decision_age_frames", 3), ("context", "private/model.pt")):
        audit = copy.deepcopy(valid)
        audit[key] = value
        row = _row(valid)
        row["gate_tracks"][0]["human_guard_decision_audit"] = audit
        invalid.append(row)
    older = _row(valid)
    older["gate_tracks"][0].pop("human_guard_decision_audit")
    _write_trace(tmp_path, monkeypatch, [older, *invalid])
    result = benchmark_trace.diagnose_trace(3, [4], tracking_ids=[7])["items"][0]
    assert "human_guard_audit" not in result
    assert result["gate_span_audit"]["near_no_span"][0]["track_id"] == 7
