import json


def _write_trace_scope_rows(bt, session_id, rows):
    bt.trace_path(session_id).write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_v0557_unidentified_neighbor_span_is_time_window_evidence(monkeypatch, tmp_path):
    import app.benchmark_trace as bt
    monkeypatch.setattr(bt, "TRACE_ROOT", tmp_path)
    rows = [{"source_time_seconds": time, "detections": 2, "tracks": 1, "road_tracks": 1,
             "gate_tracks": [{"track_id": 5, "label": "motorcycle", "anchor_signed": signed,
                              "center_signed": signed}]}
            for time, signed in [(9.9, -0.02), (10.1, 0.02)]]
    _write_trace_scope_rows(bt, 82, rows)
    item = bt.diagnose_trace(82, [10.0])["items"][0]
    # This motorcycle's span does not identify a missed bicycle in the same
    # time window. Preserve the diagnostic hint, mark its actual provenance.
    assert item["reason"] == "crossing_anchor_span_reject"
    assert item["gate_span_audit"]["anchor_span"][0]["track_id"] == 5
    assert item["diagnosis_scope"] == {
        "reason": "nearby_time_window", "geometry": "nearby_time_window",
        "counters": "frame_global", "tracking_id": None,
    }
    assert item["gate_span_audit"]["geometry_scope"] == "nearby_time_window"


def test_v0557_matched_geometry_filters_neighbor_span_before_reason_selection(monkeypatch, tmp_path):
    import app.benchmark_trace as bt
    monkeypatch.setattr(bt, "TRACE_ROOT", tmp_path)
    rows = [{"source_time_seconds": time, "detections": 2, "tracks": 2, "road_tracks": 2,
             "gate_tracks": [
                 {"track_id": 4, "label": "bicycle", "anchor_signed": 0.01, "center_signed": 0.03},
                 {"track_id": 5, "label": "motorcycle", "anchor_signed": signed, "center_signed": signed},
             ]} for time, signed in [(9.9, -0.02), (10.1, 0.02)]]
    _write_trace_scope_rows(bt, 83, rows)
    item = bt.diagnose_trace(83, [10.0], tracking_ids=[4])["items"][0]
    assert item["reason"] == "crossing_near_no_span"
    assert item["gate_span_audit"]["anchor_span"] == []
    assert [entry["track_id"] for entry in item["gate_span_audit"]["near_no_span"]] == [4]
    assert item["diagnosis_scope"] == {
        "reason": "matched_track_geometry", "geometry": "matched_track",
        "counters": "frame_global", "tracking_id": 4,
    }
    assert item["gate_span_audit"]["geometry_scope"] == "matched_track"


def test_v0557_frame_global_rejection_reasons_stay_unverified_with_matched_geometry(monkeypatch, tmp_path):
    import app.benchmark_trace as bt
    monkeypatch.setattr(bt, "TRACE_ROOT", tmp_path)
    cases = [
        ("detector_miss", {"detections": 0}, {}),
        ("tracker_miss", {"tracks": 0}, {}),
        ("road_zone_reject", {"road_tracks": 0}, {}),
        ("road_zone_reject", {}, {"rejected_outside_road": 1}),
        ("crossing_cooldown_reject", {}, {"rejected_cooldown": 1}),
        ("crossing_confirmation_reject", {}, {"rejected_unconfirmed_side": 1}),
    ]
    for expected_reason, frame_totals, later_counter in cases:
        rows = [{"source_time_seconds": time, "detections": 2, "tracks": 2, "road_tracks": 2,
                 "gate_tracks": [{"track_id": 4, "anchor_signed": signed, "center_signed": signed}],
                 **frame_totals} for time, signed in [(9.9, -0.02), (10.1, 0.02)]]
        rows[-1].update(later_counter)
        _write_trace_scope_rows(bt, 84, rows)
        item = bt.diagnose_trace(84, [10.0], tracking_ids=[4])["items"][0]
        assert item["reason"] == expected_reason
        assert item["gate_span_audit"]["anchor_span"][0]["track_id"] == 4
        assert item["diagnosis_scope"]["geometry"] == "matched_track"
        assert item["diagnosis_scope"]["reason"] == "nearby_time_window"
        assert item["diagnosis_scope"]["counters"] == "frame_global"


def test_v0557_unknown_requested_track_has_no_matched_geometry(monkeypatch, tmp_path):
    import app.benchmark_trace as bt
    monkeypatch.setattr(bt, "TRACE_ROOT", tmp_path)
    rows = [{"source_time_seconds": time, "detections": 1, "tracks": 1, "road_tracks": 1,
             "gate_tracks": [{"track_id": 5, "anchor_signed": signed, "center_signed": signed}]}
            for time, signed in [(9.9, -0.02), (10.1, 0.02)]]
    _write_trace_scope_rows(bt, 85, rows)
    item = bt.diagnose_trace(85, [10.0], tracking_ids=[99])["items"][0]
    assert item["reason"] == "crossing_gate_miss"
    assert item["gate_span_audit"]["anchor_span"] == []
    assert item["diagnosis_scope"] == {
        "reason": "nearby_time_window", "geometry": "no_track_evidence",
        "counters": "frame_global", "tracking_id": 99,
    }


def test_v0557_empty_window_does_not_claim_requested_track_evidence(monkeypatch, tmp_path):
    import app.benchmark_trace as bt
    monkeypatch.setattr(bt, "TRACE_ROOT", tmp_path)
    assert bt.diagnose_trace(86, [10.0], tracking_ids=[4])["available"] is False
    bt.trace_path(86).write_text("", encoding="utf-8")
    item = bt.diagnose_trace(86, [10.0], tracking_ids=[4])["items"][0]
    assert item["reason"] == "no_trace_window"
    assert item["diagnosis_scope"] == {
        "reason": "no_trace_window", "geometry": "no_track_evidence",
        "counters": "no_trace_window", "tracking_id": 4,
    }
    assert item["gate_span_audit"]["geometry_scope"] == "no_track_evidence"


def test_v0557_audit_only_geometry_does_not_invent_frame_counter_evidence(monkeypatch, tmp_path):
    import app.benchmark_trace as bt
    monkeypatch.setattr(bt, "TRACE_ROOT", tmp_path)
    rows = [{"source_time_seconds": time, "audit_only": True,
             "gate_tracks": [{"track_id": 4, "anchor_signed": signed, "center_signed": signed}]}
            for time, signed in [(9.9, -0.02), (10.1, 0.02)]]
    _write_trace_scope_rows(bt, 87, rows)
    item = bt.diagnose_trace(87, [10.0], tracking_ids=[4])["items"][0]
    assert item["reason"] == "no_trace_window"
    assert item["gate_span_audit"]["anchor_span"][0]["track_id"] == 4
    assert item["diagnosis_scope"]["geometry"] == "matched_track"
    assert item["diagnosis_scope"]["reason"] == "no_trace_window"
    assert item["diagnosis_scope"]["counters"] == "no_trace_window"


def test_v0557_far_matched_track_does_not_turn_missing_gate_into_proven_failure(monkeypatch, tmp_path):
    import app.benchmark_trace as bt
    monkeypatch.setattr(bt, "TRACE_ROOT", tmp_path)
    _write_trace_scope_rows(bt, 88, [{"source_time_seconds": 10.0,
        "detections": 1, "tracks": 1, "road_tracks": 1,
        "gate_tracks": [{"track_id": 4, "anchor_signed": 0.2, "center_signed": 0.3}]}])
    item = bt.diagnose_trace(88, [10.0], tracking_ids=[4])["items"][0]
    assert item["reason"] == "crossing_gate_miss"
    assert item["diagnosis_scope"]["geometry"] == "matched_track"
    assert item["diagnosis_scope"]["reason"] == "nearby_time_window"
    assert item["diagnosis_scope"]["counters"] == "frame_global"


def test_v0541_gate_span_audit_splits_anchor_center_and_near(monkeypatch, tmp_path):
    import app.benchmark_trace as bt
    monkeypatch.setattr(bt, "TRACE_ROOT", tmp_path)
    path = bt.trace_path(77)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"source_time_seconds": 9.9, "detections": 1, "tracks": 1, "road_tracks": 1,
         "rejected_outside_road": 0, "rejected_unconfirmed_side": 0, "rejected_cooldown": 0,
         "road_edge_rescues": 0, "crossing_events": 0,
         "gate_tracks": [{"track_id": 4, "label": "motorcycle", "anchor_signed": -0.02, "center_signed": -0.01}]},
        {"source_time_seconds": 10.1, "detections": 1, "tracks": 1, "road_tracks": 1,
         "rejected_outside_road": 0, "rejected_unconfirmed_side": 0, "rejected_cooldown": 0,
         "road_edge_rescues": 0, "crossing_events": 0,
         "gate_tracks": [{"track_id": 4, "label": "motorcycle", "anchor_signed": 0.02, "center_signed": 0.01}],
         "bicycle_xframe_decision_audit": [{"track_id": 4, "reason": "insufficient_frames", "accepted": False}]},
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    item = bt.diagnose_trace(77, [10.0])["items"][0]
    assert item["reason"] == "crossing_anchor_span_reject"
    assert item["gate_span_audit"]["anchor_span"][0]["track_id"] == 4
    assert item["bicycle_xframe_audit"][0]["reason"] == "insufficient_frames"


def test_v0554_context_audit_preserves_source_scores_and_final_guard_status(monkeypatch, tmp_path):
    import app.benchmark_trace as bt
    monkeypatch.setattr(bt, "TRACE_ROOT", tmp_path)
    proposal = {"kind": "bicycle_context", "track_id": 4, "frame_index": 250,
                "branch": "temporal", "decision_accepted": True, "commit_status": "pending",
                "observations": [{"frame_index": 249, "source": "general", "bicycle": 0.6, "motorcycle": 0.7}]}
    rejected = {**proposal, "commit_status": "rejected"}
    legacy = {"track_id": 4, "reason": "insufficient_frames", "accepted": False}
    rows = [{"source_time_seconds": 10.0, "bicycle_xframe_decision_audit": [legacy, proposal]},
            {"source_time_seconds": 10.2, "bicycle_xframe_decision_audit": [legacy, proposal, rejected]}]
    bt.trace_path(78).write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    item = bt.diagnose_trace(78, [10.0])["items"][0]
    assert item["bicycle_context_audit"] == [rejected]
    assert item["gate_span_audit"]["bicycle_context_audit"] == [rejected]
    assert all(audit.get("kind") != "bicycle_context" for audit in item["bicycle_xframe_audit"])
    assert rejected["decision_accepted"] is True  # Proposal accepted; guard rejected.
    assert rejected["observations"][0]["motorcycle"] == 0.7


def test_v0554_context_audit_bounds_distinct_decisions_not_repeated_snapshots():
    from app.benchmark_trace import _gate_span_audit
    records = [{"kind": "bicycle_context", "track_id": i, "frame_index": 250,
                "commit_status": "pending"} for i in range(10)]
    accepted = {**records[0], "commit_status": "accepted"}
    rows = [{"bicycle_xframe_decision_audit": records},
            {"bicycle_xframe_decision_audit": records + [accepted] * 12}]
    audit = _gate_span_audit(rows)
    assert [item["track_id"] for item in audit["bicycle_context_audit"]] == list(range(3, 10)) + [0]
    assert audit["bicycle_context_audit"][-1]["commit_status"] == "accepted"
    assert audit["bicycle_xframe_audit"] == []


def test_v0554_eof_audit_only_does_not_invent_cooldown_rejections(monkeypatch, tmp_path):
    import app.benchmark_trace as bt
    monkeypatch.setattr(bt, "TRACE_ROOT", tmp_path)
    pending = {"kind": "bicycle_context", "track_id": 4, "frame_index": 250,
               "commit_status": "pending"}
    expired = {**pending, "commit_status": "expired"}
    rows = [{"source_time_seconds": 10.0, "detections": 1, "tracks": 1, "road_tracks": 1,
             "rejected_cooldown": 7, "bicycle_xframe_decision_audit": [pending]},
            {"source_time_seconds": 10.0, "audit_only": True,
             "bicycle_xframe_decision_audit": [expired]}]
    bt.trace_path(79).write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    item = bt.diagnose_trace(79, [10.0])["items"][0]
    assert item["cooldown_reject_delta"] == 0
    assert item["reason"] == "crossing_gate_miss"
    assert item["bicycle_context_audit"] == [expired]
    bt.trace_path(79).write_text(json.dumps(rows[-1]) + "\n")
    audit_only = bt.diagnose_trace(79, [10.0])["items"][0]
    assert audit_only["reason"] == "no_trace_window"
    assert audit_only["bicycle_context_audit"] == [expired]


def test_v0555_matched_track_audit_is_selected_before_dense_scene_limit(monkeypatch, tmp_path):
    import app.benchmark_trace as bt
    monkeypatch.setattr(bt, "TRACE_ROOT", tmp_path)
    records = [{"kind": "bicycle_context", "track_id": i, "frame_index": 250,
                "commit_status": "rejected"} for i in range(12)]
    bt.trace_path(80).write_text(json.dumps({"source_time_seconds": 10.0,
        "bicycle_xframe_decision_audit": records}) + "\n")
    result = bt.diagnose_trace(80, [10.0, 10.0], tracking_ids=[0, 11])
    assert [item["bicycle_context_audit"] for item in result["items"]] == [[records[0]], [records[11]]]
    unknown = bt.diagnose_trace(80, [10.0])["items"][0]
    assert len(unknown["bicycle_context_audit"]) == 8


def test_v0555_delayed_guard_outcome_updates_original_crossing_only(monkeypatch, tmp_path):
    import app.benchmark_trace as bt
    monkeypatch.setattr(bt, "TRACE_ROOT", tmp_path)
    proposal = {"kind": "bicycle_context", "track_id": 4, "frame_index": 250,
                "commit_status": "pending", "decision_accepted": True}
    accepted = {**proposal, "commit_status": "accepted"}
    later = {**proposal, "frame_index": 450, "commit_status": "rejected"}
    rows = [{"source_time_seconds": 10.0, "detections": 1, "tracks": 1, "road_tracks": 1,
             "rejected_cooldown": 3, "bicycle_xframe_decision_audit": [proposal]},
            {"source_time_seconds": 12.0, "rejected_cooldown": 99,
             "bicycle_xframe_decision_audit": [accepted, later]}]
    bt.trace_path(81).write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    item = bt.diagnose_trace(81, [10.0], tracking_ids=[4])["items"][0]
    assert item["bicycle_context_audit"] == [accepted]
    assert item["cooldown_reject_delta"] == 0
    assert item["max_det"] == 1


def test_v0555_trace_track_filters_do_not_mix_legacy_or_gate_geometry():
    from app.benchmark_trace import _gate_span_audit
    rows = [{"bicycle_xframe_decision_audit": [{"track_id": 5, "accepted": True}],
             "gate_tracks": [{"track_id": 5, "anchor_signed": -0.1, "center_signed": -0.1}]},
            {"gate_tracks": [{"track_id": 5, "anchor_signed": 0.1, "center_signed": 0.1}]}]
    audit = _gate_span_audit(rows, tracking_id=4)
    assert audit["bicycle_xframe_audit"] == []
    assert audit["anchor_span"] == []
    assert _gate_span_audit(rows)["anchor_span"][0]["track_id"] == 5


def test_v0555_trace_schema_rejects_misaligned_tracking_ids():
    import pytest
    from pydantic import ValidationError
    from app.schemas import BenchmarkTraceDiagnoseRequest
    assert BenchmarkTraceDiagnoseRequest(times=[10, 20]).tracking_ids is None
    assert BenchmarkTraceDiagnoseRequest(times=[10, 20], tracking_ids=[4, None]).tracking_ids == [4, None]
    with pytest.raises(ValidationError):
        BenchmarkTraceDiagnoseRequest(times=[10, 20], tracking_ids=[4])
