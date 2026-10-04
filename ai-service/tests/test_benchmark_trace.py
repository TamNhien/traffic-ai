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


def test_v0558_closed_trace_camera_artifact_shares_exact_canonical_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark_trace, "TRACE_ROOT", tmp_path / "benchmark-traces")
    source = benchmark_trace.trace_path(17)
    source.parent.mkdir()
    evidence = b'{"camera_id":3,"session_id":17,"frame_index":10}\n'
    with source.open("wb") as writer:
        writer.write(evidence)

    result = benchmark_trace.publish_closed_trace(3, 17, snapshot_root=tmp_path)

    target = tmp_path / result["path"]
    assert result == {"path": "camera_3/session_17_benchmark-trace.jsonl", "bytes": len(evidence), "method": "hardlink"}
    assert target.read_bytes() == source.read_bytes() == evidence
    assert source.samefile(target)
    assert sorted(p.name for p in target.parent.iterdir()) == [target.name]


def test_v0558_camera_trace_replaces_stale_artifact_without_touching_other_session(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark_trace, "TRACE_ROOT", tmp_path / "benchmark-traces")
    benchmark_trace.TRACE_ROOT.mkdir()
    folder = tmp_path / "camera_3"
    folder.mkdir()
    stale = folder / "session_17_benchmark-trace.jsonl"
    stale.write_bytes(b"stale")
    other = folder / "session_18_benchmark-trace.jsonl"
    other.write_bytes(b"other session")
    source = benchmark_trace.trace_path(17)
    source.write_bytes(b"complete evidence\n")

    result = benchmark_trace.publish_closed_trace(3, 17, snapshot_root=tmp_path)

    assert stale.read_bytes() == b"complete evidence\n"
    assert source.samefile(stale)
    assert other.read_bytes() == b"other session"
    assert result["path"] == "camera_3/session_17_benchmark-trace.jsonl"
    assert sorted(p.name for p in folder.iterdir()) == sorted([stale.name, other.name])


def test_v0558_camera_trace_copy_fallback_preserves_bytes_and_canonical_endpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark_trace, "TRACE_ROOT", tmp_path / "benchmark-traces")
    benchmark_trace.TRACE_ROOT.mkdir()
    source = benchmark_trace.trace_path(19)
    evidence = b'{"frame_index":1}\n{"frame_index":2}\n'
    source.write_bytes(evidence)

    def unavailable_link(*_args):
        raise OSError("Hardlinks unsupported")

    monkeypatch.setattr(benchmark_trace.os, "link", unavailable_link)
    result = benchmark_trace.publish_closed_trace(4, 19, snapshot_root=tmp_path)

    target = tmp_path / result["path"]
    assert result["method"] == "copy"
    assert target.read_bytes() == source.read_bytes() == evidence
    assert not source.samefile(target)
    assert benchmark_trace.trace_path(19) == source
    assert sorted(p.name for p in target.parent.iterdir()) == [target.name]


def test_v0558_failed_trace_copy_never_publishes_partial_artifact(tmp_path, monkeypatch):
    import pytest
    monkeypatch.setattr(benchmark_trace, "TRACE_ROOT", tmp_path / "benchmark-traces")
    benchmark_trace.TRACE_ROOT.mkdir()
    source = benchmark_trace.trace_path(20)
    source.write_bytes(b"whole trace\n")
    folder = tmp_path / "camera_4"
    folder.mkdir()
    target = folder / "session_20_benchmark-trace.jsonl"
    target.write_bytes(b"previous complete artifact\n")

    def unavailable_link(*_args):
        raise OSError("Hardlinks unsupported")

    def failed_copy(_source, temporary):
        temporary.write_bytes(b"partial")
        raise OSError("No space left on device")

    monkeypatch.setattr(benchmark_trace.os, "link", unavailable_link)
    monkeypatch.setattr(benchmark_trace.shutil, "copyfile", failed_copy)
    with pytest.raises(OSError):
        benchmark_trace.publish_closed_trace(4, 20, snapshot_root=tmp_path)

    assert source.read_bytes() == b"whole trace\n"
    assert target.read_bytes() == b"previous complete artifact\n"
    assert sorted(p.name for p in folder.iterdir()) == [target.name]


def test_v0558_missing_canonical_trace_creates_no_camera_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark_trace, "TRACE_ROOT", tmp_path / "benchmark-traces")

    assert benchmark_trace.publish_closed_trace(4, 21, snapshot_root=tmp_path) is None
    assert list(tmp_path.iterdir()) == []


def test_v0558_trace_session_header_does_not_invent_diagnostic_frame(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark_trace, "TRACE_ROOT", tmp_path)
    rows = [
        {"kind": "session_metadata", "audit_only": True, "camera_id": 4, "session_id": 22, "source_fps": 25.0},
        {"frame_index": 1, "source_time_seconds": 0.0, "detections": 2, "tracks": 2, "road_tracks": 2, "crossing_events": 1},
    ]
    benchmark_trace.trace_path(22).write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    result = benchmark_trace.diagnose_trace(22, [0.0, 1.0], window_seconds=.1)

    assert result["items"][0]["max_det"] == 2
    assert result["items"][0]["crossing_events_nearby"] == 1
    assert result["items"][1]["reason"] == "no_trace_window"
