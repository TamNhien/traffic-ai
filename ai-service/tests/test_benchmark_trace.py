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
