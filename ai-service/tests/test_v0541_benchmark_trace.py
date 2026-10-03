import json


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
