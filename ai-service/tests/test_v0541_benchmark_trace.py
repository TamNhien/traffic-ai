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
