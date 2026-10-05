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


def test_v0559_closed_gzip_preserves_every_original_byte_and_hash(tmp_path, monkeypatch):
    import gzip
    from hashlib import sha256
    monkeypatch.setattr(benchmark_trace, "TRACE_ROOT", tmp_path)
    source = benchmark_trace.trace_path(22)
    evidence = ('{"frame_index":1,"note":"xe đạp"}\n' * 1000).encode()
    source.write_bytes(evidence)
    assert benchmark_trace.closed_compressed_trace(22) is None

    metadata = benchmark_trace.publish_compressed_trace(22)
    path, served = benchmark_trace.closed_compressed_trace(22)

    compressed = path.read_bytes()
    assert gzip.decompress(compressed) == evidence
    assert metadata == served
    assert metadata["source_bytes"] == len(evidence)
    assert metadata["source_sha256"] == sha256(evidence).hexdigest()
    assert metadata["compressed_sha256"] == sha256(compressed).hexdigest()
    assert metadata["compressed_bytes"] == len(compressed) < len(evidence)
    assert source.read_bytes() == evidence


def test_v0559_live_or_replaced_trace_cannot_reuse_closed_certificate(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark_trace, "TRACE_ROOT", tmp_path)
    source = benchmark_trace.trace_path(23)
    source.write_bytes(b'{"frame_index":1}\n')
    benchmark_trace.publish_compressed_trace(23)
    assert benchmark_trace.closed_compressed_trace(23) is not None
    with source.open("ab") as handle:
        handle.write(b'{"frame_index":2}\n')
    assert benchmark_trace.closed_compressed_trace(23) is None
    benchmark_trace.publish_compressed_trace(23)
    replacement = tmp_path / "replacement"
    replacement.write_bytes(source.read_bytes())
    replacement.replace(source)
    assert benchmark_trace.closed_compressed_trace(23) is None


def test_v0559_partial_gzip_failure_leaves_raw_camera_evidence_usable(tmp_path, monkeypatch):
    import pytest
    monkeypatch.setattr(benchmark_trace, "TRACE_ROOT", tmp_path / "benchmark-traces")
    benchmark_trace.TRACE_ROOT.mkdir()
    source = benchmark_trace.trace_path(24)
    source.write_bytes(b"original evidence\n" * 100)
    raw = benchmark_trace.publish_closed_trace(1, 24, snapshot_root=tmp_path)

    def fail_write(self, data):
        self.handle.write(b"partial")
        raise OSError("disk full")

    monkeypatch.setattr(benchmark_trace._BoundedCompressedWriter, "write", fail_write)
    with pytest.raises(OSError):
        benchmark_trace.publish_compressed_trace(24)
    assert benchmark_trace.closed_compressed_trace(24) is None
    assert (tmp_path / raw["path"]).read_bytes() == source.read_bytes()
    assert sorted(p.name for p in benchmark_trace.TRACE_ROOT.iterdir()) == [source.name]


def test_v0559_gzip_transport_bound_is_enforced_before_publication(tmp_path, monkeypatch):
    import pytest
    monkeypatch.setattr(benchmark_trace, "TRACE_ROOT", tmp_path)
    monkeypatch.setattr(benchmark_trace, "TRACE_EXPORT_MAX_BYTES", 5)
    source = benchmark_trace.trace_path(25)
    source.write_bytes(b'{"frame_index":1}\n')
    with pytest.raises(OSError):
        benchmark_trace.publish_compressed_trace(25)
    assert benchmark_trace.closed_compressed_trace(25) is None
    assert list(tmp_path.iterdir()) == [source]


def test_v0559_trace_changed_during_compression_cannot_publish_closed_metadata(tmp_path, monkeypatch):
    import pytest
    monkeypatch.setattr(benchmark_trace, "TRACE_ROOT", tmp_path)
    source = benchmark_trace.trace_path(28)
    source.write_bytes(b'{"frame_index":1}\n')
    original = benchmark_trace._BoundedCompressedWriter.write
    changes = []

    def append_during_write(self, data):
        if not changes:
            with source.open("ab") as live_writer:
                live_writer.write(b'{"frame_index":2}\n')
            changes.append(True)
        return original(self, data)

    monkeypatch.setattr(benchmark_trace._BoundedCompressedWriter, "write", append_during_write)
    with pytest.raises(OSError):
        benchmark_trace.publish_compressed_trace(28)
    assert benchmark_trace.closed_compressed_trace(28) is None
    assert list(tmp_path.iterdir()) == [source]


def test_v0559_failed_closed_certificate_never_exposes_compressed_artifact(tmp_path, monkeypatch):
    import pytest
    from pathlib import Path
    monkeypatch.setattr(benchmark_trace, "TRACE_ROOT", tmp_path)
    source = benchmark_trace.trace_path(29)
    source.write_bytes(b'{"frame_index":1}\n')
    original = Path.write_text

    def failed_metadata(path, *args, **options):
        if ".closed.json." in path.name:
            raise OSError("certificate storage full")
        return original(path, *args, **options)

    monkeypatch.setattr(Path, "write_text", failed_metadata)
    with pytest.raises(OSError):
        benchmark_trace.publish_compressed_trace(29)
    assert benchmark_trace.closed_compressed_trace(29) is None
    assert list(tmp_path.iterdir()) == [source]


def test_v0559_short_compressed_write_is_never_accepted():
    import pytest
    from types import SimpleNamespace
    writer = benchmark_trace._BoundedCompressedWriter(SimpleNamespace(write=lambda _data: 1))
    with pytest.raises(OSError):
        writer.write(b"partial write")


def test_v0559_changed_gzip_or_invalid_certificate_is_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark_trace, "TRACE_ROOT", tmp_path)
    source = benchmark_trace.trace_path(26)
    source.write_bytes(b'{"frame_index":1}\n')
    benchmark_trace.publish_compressed_trace(26)
    compressed = benchmark_trace.compressed_trace_path(26)
    compressed.write_bytes(b"modified")
    assert benchmark_trace.closed_compressed_trace(26) is None
    benchmark_trace._closed_trace_metadata_path(26).write_text("[]")
    assert benchmark_trace.closed_compressed_trace(26) is None


def test_v0559_gzip_route_serves_closed_attachment_without_http_inflation(tmp_path, monkeypatch):
    import ast
    from pathlib import Path
    from types import SimpleNamespace
    import pytest
    monkeypatch.setattr(benchmark_trace, "TRACE_ROOT", tmp_path)
    source = benchmark_trace.trace_path(27)
    source.write_bytes(b'{"frame_index":1}\n')
    path = Path(__file__).parents[1] / "app/main.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in {"benchmark_trace_download", "benchmark_trace_download_gzip"}]
    for function in functions:
        function.decorator_list = []

    class HTTPError(Exception):
        def __init__(self, status_code, detail):
            self.status_code = status_code

    def file_response(path, **options):
        return SimpleNamespace(path=path, **options)

    namespace = {"trace_path":benchmark_trace.trace_path,
                 "closed_compressed_trace":benchmark_trace.closed_compressed_trace,
                 "FileResponse":file_response, "HTTPException":HTTPError}
    exec(compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])), str(path), "exec"), namespace)
    raw = namespace["benchmark_trace_download"](27)
    assert raw.path == source and raw.media_type == "application/x-ndjson"
    with pytest.raises(HTTPError) as error:
        namespace["benchmark_trace_download_gzip"](27)
    assert error.value.status_code == 404
    metadata = benchmark_trace.publish_compressed_trace(27)
    zipped = namespace["benchmark_trace_download_gzip"](27)
    assert zipped.filename == "session_27.jsonl.gz" and zipped.media_type == "application/gzip"
    assert "Content-Encoding" not in zipped.headers
    assert zipped.headers["X-Traffic-AI-Trace-Source-SHA256"] == metadata["source_sha256"]
    assert zipped.headers["X-Traffic-AI-Trace-Closed"] == "true"


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
