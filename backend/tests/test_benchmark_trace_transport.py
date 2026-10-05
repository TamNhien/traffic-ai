"""Actual optional transport function with explicit HTTP fixtures; no networking."""
import ast
from contextlib import nullcontext
import gzip
from hashlib import sha256
from pathlib import Path
import re
import time
from types import SimpleNamespace

from app.benchmarking import (
    BENCHMARK_TRACE_EXPORT_MAX_BYTES, BenchmarkTraceArchive, BenchmarkTraceTooLarge,
    read_benchmark_trace_chunks,
)


def _transport(responses):
    requests = []

    def stream(method, url, **options):
        requests.append((method, url, options))
        return nullcontext(responses.pop(0))

    path = Path(__file__).parents[1] / "app/api/routes.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == "_fetch_benchmark_export_trace")
    namespace = {
        "time":time, "re":re, "settings":SimpleNamespace(ai_service_url="http://ai-service:8000"),
        "httpx":SimpleNamespace(stream=stream, TimeoutException=TimeoutError),
        "BENCHMARK_TRACE_EXPORT_MAX_BYTES":BENCHMARK_TRACE_EXPORT_MAX_BYTES,
        "BenchmarkTraceArchive":BenchmarkTraceArchive, "BenchmarkTraceTooLarge":BenchmarkTraceTooLarge,
        "read_benchmark_trace_chunks":read_benchmark_trace_chunks,
    }
    exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])), str(path), "exec"), namespace)
    return namespace["_fetch_benchmark_export_trace"], namespace, requests


def _response(status=200, content=b"", headers=None):
    return SimpleNamespace(status_code=status, is_success=status == 200,
                           headers=headers or {}, iter_bytes=lambda **_options: iter([content] if content else []))


def _gzip_response(original=b"complete evidence\n"):
    compressed = gzip.compress(original, mtime=0)
    return _response(content=compressed, headers={
        "Content-Length":str(len(compressed)), "X-Traffic-AI-Trace-Closed":"true",
        "X-Traffic-AI-Trace-Source-Bytes":str(len(original)),
        "X-Traffic-AI-Trace-Source-SHA256":sha256(original).hexdigest(),
        "X-Traffic-AI-Trace-Compressed-SHA256":sha256(compressed).hexdigest(),
    })


def test_v0559_gzip_transport_accepts_large_original_with_bounded_compressed_bytes():
    response = _gzip_response()
    response.headers["X-Traffic-AI-Trace-Source-Bytes"] = "140618731"
    fetch, _namespace, requests = _transport([response])
    payload, reason = fetch(163)
    assert reason == "available" and isinstance(payload, BenchmarkTraceArchive)
    assert payload.source_bytes == 140618731 > BENCHMARK_TRACE_EXPORT_MAX_BYTES
    assert len(payload.content) < BENCHMARK_TRACE_EXPORT_MAX_BYTES
    assert len(requests) == 1 and requests[0][1].endswith("/163/download-gzip")
    assert requests[0][2] == {"timeout":8.0, "follow_redirects":False}


def test_v0559_missing_gzip_falls_back_to_legacy_raw_without_changing_bytes():
    raw = b'{"frame_index":1}\n'
    fetch, _namespace, requests = _transport([_response(404), _response(content=raw)])
    assert fetch(8) == (raw, "available")
    assert [request[1].rsplit("/", 1)[-1] for request in requests] == ["download-gzip", "download"]


def test_v0559_gzip_transport_rejects_truncated_body_or_wrong_hash():
    for failure in ("length", "hash", "closed", "source", "content_encoding"):
        response = _gzip_response()
        if failure == "length":
            response.headers["Content-Length"] = "999"
        elif failure == "hash":
            response.headers["X-Traffic-AI-Trace-Compressed-SHA256"] = "0" * 64
        elif failure == "closed":
            response.headers["X-Traffic-AI-Trace-Closed"] = "false"
        elif failure == "source":
            response.headers["X-Traffic-AI-Trace-Source-Bytes"] = "NaN"
        else:
            response.headers["Content-Encoding"] = "gzip"
        fetch, _namespace, requests = _transport([response])
        payload, reason = fetch(9)
        assert payload is None and reason == ("incomplete" if failure == "length" else "invalid_metadata")
        assert len(requests) == 1


def test_v0559_gzip_transport_stops_at_cap_even_without_content_length():
    response = _gzip_response()
    response.headers.pop("Content-Length")
    fetch, namespace, _requests = _transport([response])
    namespace["BENCHMARK_TRACE_EXPORT_MAX_BYTES"] = 5
    assert fetch(9) == (None, "too_large")


def test_v0559_trace_transport_keeps_total_deadline_and_rejects_interrupted_body():
    response = _gzip_response()
    fetch, namespace, _requests = _transport([response])
    clock = iter([0.0, 0.0, 21.0])
    namespace["time"] = SimpleNamespace(monotonic=lambda: next(clock))
    assert fetch(9) == (None, "timeout")

    def interrupted(**_options):
        yield b"partial"
        raise OSError("transport interrupted")

    response = _gzip_response()
    response.iter_bytes = interrupted
    fetch, _namespace, _requests = _transport([response])
    assert fetch(9) == (None, "service_unavailable")


def test_v0559_missing_or_oversized_legacy_trace_keeps_explicit_status():
    for response, expected in [(_response(404), "not_found"),
                               (_response(headers={"Content-Length":str(BENCHMARK_TRACE_EXPORT_MAX_BYTES + 1)}), "too_large")]:
        fetch, _namespace, _requests = _transport([_response(404), response])
        assert fetch(9) == (None, expected)
