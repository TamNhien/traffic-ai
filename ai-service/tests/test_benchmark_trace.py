import json

import app.benchmark_trace as benchmark_trace


def test_trace_diagnoses_detector_tracker_road_and_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark_trace, "TRACE_ROOT", tmp_path)
    path = benchmark_trace.trace_path(7)
    rows = [
        {"source_time_seconds": 1.0, "detections": 0, "tracks": 0, "road_tracks": 0, "crossing_events": 0, "rejected_outside_road": 0},
        {"source_time_seconds": 2.0, "detections": 2, "tracks": 0, "road_tracks": 0, "crossing_events": 0, "rejected_outside_road": 0},
        {"source_time_seconds": 3.0, "detections": 2, "tracks": 2, "road_tracks": 0, "crossing_events": 0, "rejected_outside_road": 1},
        {"source_time_seconds": 4.0, "detections": 2, "tracks": 2, "road_tracks": 2, "crossing_events": 0, "rejected_outside_road": 1},
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    result = benchmark_trace.diagnose_trace(7, [1.0, 2.0, 3.0, 4.0], window_seconds=0.1)
    assert result["available"] is True
    assert [item["reason"] for item in result["items"]] == [
        "detector_miss", "tracker_miss", "road_zone_reject", "crossing_gate_miss"
    ]


def test_v0540_trace_splits_anchor_center_and_near_gate_misses(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark_trace, "TRACE_ROOT", tmp_path)
    path = benchmark_trace.trace_path(8)
    rows = [
        {
            "source_time_seconds": 1.00,
            "detections": 2,
            "tracks": 2,
            "road_tracks": 2,
            "crossing_events": 0,
            "rejected_outside_road": 0,
            "rejected_unconfirmed_side": 0,
            "rejected_cooldown": 0,
            "road_edge_rescues": 0,
            "gate_tracks": [{"track_id": 10, "anchor_d": -0.020, "center_d": -0.018}],
        },
        {
            "source_time_seconds": 1.10,
            "detections": 2,
            "tracks": 2,
            "road_tracks": 2,
            "crossing_events": 0,
            "rejected_outside_road": 0,
            "rejected_unconfirmed_side": 0,
            "rejected_cooldown": 0,
            "road_edge_rescues": 0,
            "gate_tracks": [{"track_id": 10, "anchor_d": 0.021, "center_d": 0.020}],
        },
        {
            "source_time_seconds": 2.00,
            "detections": 2,
            "tracks": 2,
            "road_tracks": 2,
            "crossing_events": 0,
            "rejected_outside_road": 0,
            "rejected_unconfirmed_side": 0,
            "rejected_cooldown": 0,
            "road_edge_rescues": 0,
            "gate_tracks": [{"track_id": 20, "anchor_d": -0.004, "center_d": -0.020}],
        },
        {
            "source_time_seconds": 2.10,
            "detections": 2,
            "tracks": 2,
            "road_tracks": 2,
            "crossing_events": 0,
            "rejected_outside_road": 0,
            "rejected_unconfirmed_side": 0,
            "rejected_cooldown": 0,
            "road_edge_rescues": 0,
            "gate_tracks": [{"track_id": 20, "anchor_d": 0.004, "center_d": 0.020}],
        },
        {
            "source_time_seconds": 3.00,
            "detections": 2,
            "tracks": 2,
            "road_tracks": 2,
            "crossing_events": 0,
            "rejected_outside_road": 0,
            "rejected_unconfirmed_side": 0,
            "rejected_cooldown": 0,
            "road_edge_rescues": 0,
            "gate_tracks": [{"track_id": 30, "anchor_d": -0.010, "center_d": -0.009}],
        },
        {
            "source_time_seconds": 3.10,
            "detections": 2,
            "tracks": 2,
            "road_tracks": 2,
            "crossing_events": 0,
            "rejected_outside_road": 0,
            "rejected_unconfirmed_side": 0,
            "rejected_cooldown": 0,
            "road_edge_rescues": 0,
            "gate_tracks": [{"track_id": 30, "anchor_d": -0.003, "center_d": -0.002}],
        },
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    result = benchmark_trace.diagnose_trace(8, [1.05, 2.05, 3.05], window_seconds=0.11)
    assert [item["reason"] for item in result["items"]] == [
        "crossing_anchor_span_reject",
        "crossing_center_only_span",
        "crossing_near_no_span",
    ]
    assert result["items"][0]["anchor_span_tracks"] == [10]
    assert result["items"][1]["center_span_tracks"] == [20]
