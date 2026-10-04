from types import SimpleNamespace

from app.benchmarking import match_crossings


def item(idx, time, direction="in", vehicle_type="motorcycle"):
    return SimpleNamespace(id=idx, source_time_seconds=time, direction=direction, vehicle_type=vehicle_type)


def test_benchmark_exact_match() -> None:
    result = match_crossings([item(1, 1.0)], [item(11, 1.02)], 0.10)
    assert result["matched"] == 1
    assert result["missed"] == 0
    assert result["false_positives"] == 0
    assert result["counting_recall"] == 1.0


def test_v0555_equal_timestamp_report_is_independent_of_input_order() -> None:
    from itertools import permutations

    gt = [item(1, 10.0, "in", "bicycle"), item(2, 10.0, "out", "truck")]
    ai = [item(11, 10.0, "in", "bicycle"), item(12, 10.0, "out", "truck")]
    reference = match_crossings(gt, ai, 0.10)
    for gt_order in permutations(gt):
        for ai_order in permutations(ai):
            assert match_crossings(gt_order, ai_order, 0.10) == reference
    assert reference["matched"] == 2
    assert reference["direction_accuracy"] == 1.0
    assert reference["class_accuracy"] == 1.0


def test_v0555_equal_gt_time_retains_temporal_objective_and_id_ties() -> None:
    gt = [item(2, 10.0, "out", "bicycle"), item(1, 10.0, "in", "motorcycle")]
    ai = [item(12, 10.04, "in", "motorcycle"), item(11, 9.96, "out", "bicycle")]
    result = match_crossings(gt, ai, 0.10)
    assert result["matched"] == 2
    assert [(pair["ground_truth_id"], pair["ai_event_id"]) for pair in result["matched_items"]] == [(1, 11), (2, 12)]
    # Neither class nor direction is used to repair the equal-time pairing.
    assert result["direction_accuracy"] == 0.0
    assert result["class_accuracy"] == 0.0
    assert sum(abs(pair["delta_seconds"]) for pair in result["matched_items"]) == 0.08


def test_v0555_equal_ai_time_false_positive_attribution_is_stable() -> None:
    gt = [item(1, 10.0, "in", "bicycle")]
    ai = [item(11, 10.0, "in", "bicycle"), item(12, 10.0, "out", "motorcycle")]
    first = match_crossings(gt, ai, 0.10)
    second = match_crossings(gt, reversed(ai), 0.10)
    assert first == second
    assert first["matched_items"][0]["ai_event_id"] == 12
    assert first["class_accuracy"] == 0.0
    assert first["direction_accuracy"] == 0.0
    assert first["false_positive_items"][0]["ai_event_id"] == 11


def test_benchmark_reports_missed_and_false_positive() -> None:
    gt = [item(1, 1.0), item(2, 5.0, "out", "truck")]
    ai = [item(11, 1.02), item(12, 8.0, "out", "truck")]
    result = match_crossings(gt, ai, 0.20)
    assert result["matched"] == 1
    assert result["missed"] == 1
    assert result["false_positives"] == 1
    assert result["count_error"] == 0
    assert result["missed_items"][0]["time"] == 5.0


def test_benchmark_scores_class_separately_from_counting() -> None:
    gt = [item(1, 2.0, "in", "truck")]
    ai = [item(11, 2.03, "in", "bus")]
    result = match_crossings(gt, ai, 0.20)
    assert result["matched"] == 1
    assert result["counting_recall"] == 1.0
    assert result["class_accuracy"] == 0.0
    assert result["class_mismatches"] == 1
    assert result["class_mismatch_items"][0]["ground_truth_vehicle_type"] == "truck"
    assert result["class_mismatch_items"][0]["ai_vehicle_type"] == "bus"
    assert result["per_class"]["truck"]["ground_truth"] == 1
    assert result["per_class"]["bus"]["ai"] == 1


def test_benchmark_tolerance_blocks_far_event() -> None:
    result = match_crossings([item(1, 10.0)], [item(11, 10.9)], 0.50)
    assert result["matched"] == 0
    assert result["missed"] == 1
    assert result["false_positives"] == 1


def rich_item(idx, time, direction="in", vehicle_type="motorcycle", tracking_id=None, crossing_method=None, confidence=0.9, crossing_x=None, crossing_y=None):
    return SimpleNamespace(
        id=idx,
        source_time_seconds=time,
        direction=direction,
        vehicle_type=vehicle_type,
        tracking_id=tracking_id,
        crossing_method=crossing_method,
        confidence=confidence,
        crossing_x=crossing_x,
        crossing_y=crossing_y,
    )


def test_false_positive_analyzer_flags_startup_artifact() -> None:
    result = match_crossings([], [rich_item(21, 0.08, tracking_id=7, crossing_method="direct")], 0.75)
    assert result["false_positive_items"][0]["reason"] == "startup_artifact"
    assert result["dominant_false_positive_reason"] == "startup_artifact"


def test_false_positive_analyzer_flags_direction_flip_jitter() -> None:
    ai = [
        rich_item(31, 10.0, "in", tracking_id=55, crossing_method="direct"),
        rich_item(32, 11.0, "out", tracking_id=55, crossing_method="interpolated"),
    ]
    result = match_crossings([rich_item(1, 10.02, "in")], ai, 0.20)
    assert result["matched"] == 1
    assert result["false_positives"] == 1
    assert result["false_positive_items"][0]["reason"] == "direction_flip_jitter"


def test_false_positive_analyzer_flags_duplicate_near_matched_gt() -> None:
    ai = [
        rich_item(41, 20.00, "in", tracking_id=71, crossing_method="direct"),
        rich_item(42, 20.35, "in", tracking_id=72, crossing_method="direct"),
    ]
    result = match_crossings([rich_item(2, 20.02, "in")], ai, 0.50)
    assert result["matched"] == 1
    assert result["false_positive_items"][0]["reason"] == "duplicate_near_gt"


def test_v0527_global_temporal_matcher_avoids_greedy_pair_loss() -> None:
    # GT#1 can match either AI event, while GT#2 can only match the later one.
    # A nearest-first greedy pass would consume AI#12 for GT#1 and leave GT#2
    # unmatched. Global assignment correctly keeps both valid crossings.
    gt = [item(1, 1.0), item(2, 1.5)]
    ai = [item(11, 0.5), item(12, 1.1)]
    result = match_crossings(gt, ai, 0.60)
    assert result["matched"] == 2
    assert result["missed"] == 0
    assert result["false_positives"] == 0
    assert [pair["ai_event_id"] for pair in result["matched_items"]] == [11, 12]


def test_v0527_global_matcher_does_not_use_class_to_improve_assignment() -> None:
    gt = [item(1, 10.0, "in", "bicycle")]
    ai = [
        item(11, 9.90, "in", "motorcycle"),
        item(12, 10.40, "in", "bicycle"),
    ]
    result = match_crossings(gt, ai, 0.50)
    assert result["matched"] == 1
    assert result["matched_items"][0]["ai_event_id"] == 11
    assert result["class_mismatches"] == 1


def test_v0536_spatial_duplicate_requires_close_crossing_point() -> None:
    ai = [
        rich_item(201, 30.00, "in", tracking_id=501, crossing_method="direct", crossing_x=0.40, crossing_y=0.50),
        rich_item(202, 30.40, "in", tracking_id=502, crossing_method="rescued", crossing_x=0.41, crossing_y=0.51),
    ]
    gt = [rich_item(1, 30.02, "in", crossing_x=0.40, crossing_y=0.50)]
    result = match_crossings(gt, ai, 0.50)
    assert result["false_positive_items"][0]["reason"] == "spatial_duplicate_near_gt"


def test_v0536_near_time_but_far_crossing_is_not_called_duplicate() -> None:
    ai = [
        rich_item(211, 40.00, "in", tracking_id=601, crossing_method="direct", crossing_x=0.20, crossing_y=0.50),
        rich_item(212, 40.35, "in", tracking_id=602, crossing_method="rescued", crossing_x=0.72, crossing_y=0.50),
    ]
    gt = [rich_item(2, 40.02, "in", crossing_x=0.20, crossing_y=0.50)]
    result = match_crossings(gt, ai, 0.50)
    assert result["false_positive_items"][0]["reason"] == "rescued_gap_unmatched"


def test_v0538_spatial_duplicate_diagnostic_exposes_delta_distance_and_method() -> None:
    ai = [
        rich_item(301, 50.00, "in", tracking_id=701, crossing_method="direct", crossing_x=0.40, crossing_y=0.50),
        rich_item(302, 50.80, "in", tracking_id=702, crossing_method="rescued", crossing_x=0.405, crossing_y=0.503),
    ]
    gt = [rich_item(3, 50.01, "in", crossing_x=0.40, crossing_y=0.50)]
    result = match_crossings(gt, ai, 0.75)
    diagnostic = result["false_positive_items"][0]
    assert diagnostic["reason"] == "spatial_duplicate_near_gt"
    assert diagnostic["near_matched_time_delta"] == 0.8
    assert diagnostic["near_matched_spatial_distance"] is not None
    assert diagnostic["near_matched_spatial_distance"] < 0.008
    assert diagnostic["near_matched_crossing_method"] == "direct"
    assert "method direct" in diagnostic["detail"]


def test_v0544_unmatched_review_links_near_gt_and_ai_without_changing_scores() -> None:
    gt = [rich_item(401, 10.00, "in", "motorcycle")]
    ai = [rich_item(402, 10.92, "in", "motorcycle", tracking_id=77, crossing_method="rescued")]
    result = match_crossings(gt, ai, 0.75)
    assert result["matched"] == 0
    assert result["missed"] == 1
    assert result["false_positives"] == 1
    assert result["unmatched_review_links"] == 1
    review = result["missed_items"][0]["review_candidate"]
    assert review["ai_event_id"] == 402
    assert review["outside_scoring_window"] is True
    assert review["delta_seconds"] == 0.92
    reverse = result["false_positive_items"][0]["review_ground_truth"]
    assert reverse["ground_truth_id"] == 401
    assert reverse["outside_scoring_window"] is True
    assert reverse["delta_seconds"] == -0.92


def test_v0553_duplicate_audit_prefers_same_point_over_nearer_separate_lane() -> None:
    ai = [
        rich_item(501, 10.0, tracking_id=81, crossing_method="direct", crossing_x=0.2, crossing_y=0.5),
        rich_item(502, 11.0, tracking_id=82, crossing_method="direct", crossing_x=0.6, crossing_y=0.5),
        rich_item(503, 10.2, tracking_id=83, crossing_method="rescued", crossing_x=0.605, crossing_y=0.5),
    ]
    result = match_crossings([rich_item(51, 10.0), rich_item(52, 11.0)], ai, 0.75)
    assert result["matched"] == 2
    assert result["false_positives"] == 1
    diagnostic = result["false_positive_items"][0]
    assert diagnostic["ai_event_id"] == 503
    assert diagnostic["reason"] == "spatial_duplicate_near_gt"
    assert diagnostic["near_matched_ai_event_id"] == 502
    assert diagnostic["near_matched_time_delta"] == 0.8
    assert diagnostic["near_matched_spatial_distance"] == 0.005


def test_v0553_duplicate_audit_does_not_accuse_opposite_direct_crossing() -> None:
    ai = [
        rich_item(511, 20.0, "in", tracking_id=91, crossing_method="direct", crossing_x=0.5, crossing_y=0.5),
        rich_item(512, 20.3, "out", tracking_id=92, crossing_method="direct", crossing_x=0.5, crossing_y=0.5),
    ]
    result = match_crossings([rich_item(61, 20.0, "in")], ai, 0.75)
    diagnostic = result["false_positive_items"][0]
    assert result["matched"] == 1
    assert result["false_positives"] == 1
    assert diagnostic["reason"] == "direct_unmatched"
    assert diagnostic["near_matched_ai_event_id"] is None


def test_v0553_duplicate_audit_keeps_separate_nearby_vehicles_unmatched() -> None:
    ai = [
        rich_item(521, 30.0, tracking_id=101, crossing_method="direct", crossing_x=0.2, crossing_y=0.5),
        rich_item(522, 30.3, tracking_id=102, crossing_method="rescued", crossing_x=0.3, crossing_y=0.5),
    ]
    result = match_crossings([rich_item(71, 30.0)], ai, 0.75)
    diagnostic = result["false_positive_items"][0]
    assert diagnostic["reason"] == "rescued_gap_unmatched"
    assert diagnostic["near_matched_ai_event_id"] == 521
    assert diagnostic["near_matched_spatial_distance"] == 0.1
    assert result["matched"] == 1
    assert result["false_positives"] == 1


def test_v0554_duplicate_audit_prefers_closest_physical_crossing_inside_radius() -> None:
    ai = [
        rich_item(601, 10.0, tracking_id=111, crossing_method="direct", crossing_x=0.53, crossing_y=0.5),
        rich_item(602, 11.0, tracking_id=112, crossing_method="direct", crossing_x=0.502, crossing_y=0.5),
        rich_item(603, 10.2, tracking_id=113, crossing_method="rescued", crossing_x=0.5, crossing_y=0.5),
    ]
    result = match_crossings([rich_item(81, 10.0), rich_item(82, 11.0)], ai, 0.75)
    assert result["matched"] == 2
    assert result["missed"] == 0
    assert result["false_positives"] == 1
    diagnostic = result["false_positive_items"][0]
    assert diagnostic["ai_event_id"] == 603
    assert diagnostic["near_matched_ai_event_id"] == 602
    assert diagnostic["near_matched_time_delta"] == 0.8
    assert diagnostic["near_matched_spatial_distance"] == 0.002


def test_v0554_duplicate_audit_exact_tie_is_independent_of_candidate_order() -> None:
    from app.benchmarking import _false_positive_diagnostics, _timed

    earlier = _timed(rich_item(611, 20.0, tracking_id=121, crossing_method="direct", crossing_x=0.5, crossing_y=0.5))
    later = _timed(rich_item(612, 20.0, tracking_id=122, crossing_method="direct", crossing_x=0.5, crossing_y=0.5))
    extra = _timed(rich_item(613, 20.3, tracking_id=123, crossing_method="rescued", crossing_x=0.505, crossing_y=0.5))
    matched = [{"ai_event_id": 611}, {"ai_event_id": 612}]
    for candidates in ([earlier, later, extra], [extra, later, earlier]):
        diagnostics, _, _ = _false_positive_diagnostics([extra], candidates, matched, 0.75)
        assert diagnostics[0]["near_matched_ai_event_id"] == 611
        assert diagnostics[0]["near_matched_spatial_distance"] == 0.005


def test_v0556_diagnostics_export_reproduces_scoring_without_mutating_sources() -> None:
    import copy
    from datetime import datetime, timezone
    from hashlib import sha256
    from io import BytesIO
    import json
    from zipfile import ZipFile
    from app.benchmarking import build_benchmark_export

    marks = [
        {"id": 1, "source_time_seconds": 10.0, "direction": "in", "vehicle_type": "bicycle", "note": "Xe đạp đẩy bộ"},
        {"id": 2, "source_time_seconds": 20.0, "direction": "out", "vehicle_type": "truck"},
    ]
    events = [
        {"id": 11, "source_time_seconds": 10.1, "direction": "in", "vehicle_type": "motorcycle", "tracking_id": 77},
        {"id": 12, "source_time_seconds": 30.0, "direction": "out", "vehicle_type": "truck", "tracking_id": 88},
        {"id": 13, "source_time_seconds": None, "direction": "in", "vehicle_type": "motorcycle"},
    ]
    report = match_crossings(marks, events[:2], 0.75)
    report.update({"session_id": 9, "benchmark": {
        "id": 3, "source_url": "rtsp://admin:secret@cam.local:554/live?token=private#signed",
        "tolerance_seconds": 0.75,
    }})
    original = copy.deepcopy((report, marks, events))
    stamp = datetime(2026, 10, 4, tzinfo=timezone.utc)
    archive = build_benchmark_export(
        report=report, marks=marks, events=events,
        session={"id": 9, "started_at": stamp, "source_url": r"D:\Videos\clip1.mp4"},
        config={"current_camera": None}, exported_at=stamp,
    )
    with ZipFile(BytesIO(archive)) as zipped:
        assert zipped.testzip() is None
        exported_report = json.loads(zipped.read("report.json"))
        exported_marks = json.loads(zipped.read("ground-truth.json"))
        exported_events = json.loads(zipped.read("events.json"))
        recreated = match_crossings(exported_marks, [event for event in exported_events if event["source_time_seconds"] is not None], 0.75)
        for field in ("matched", "missed", "false_positives", "class_accuracy", "direction_accuracy", "matched_items", "missed_items", "false_positive_items"):
            assert exported_report[field] == recreated[field]
        assert len(exported_events) == 3
        assert exported_marks[0]["note"] == "Xe đạp đẩy bộ"
        assert exported_report["benchmark"]["source_url"] == "rtsp://cam.local:554/live"
        assert json.loads(zipped.read("session.json"))["source_url"] == "clip1.mp4"
        assert json.loads(zipped.read("session.json"))["started_at"] == stamp.isoformat()
        assert b"secret" not in zipped.read("report.json")
        assert b"private" not in zipped.read("report.json")
        manifest = json.loads(zipped.read("manifest.json"))
        for filename, information in manifest["files"].items():
            data = zipped.read(filename)
            assert information == {"bytes": len(data), "sha256": sha256(data).hexdigest()}
        assert "benchmark-trace.jsonl" not in zipped.namelist()
    assert (report, marks, events) == original


def test_v0556_diagnostics_export_preserves_trace_bytes_and_states_missing_evidence() -> None:
    from datetime import datetime, timezone
    from hashlib import sha256
    from io import BytesIO
    import json
    from zipfile import ZipFile
    from app.benchmarking import build_benchmark_export

    trace = b'{"frame":251,"bicycle":0.52}\n{"frame":252,"motorcycle":0.8}\n'
    arguments = dict(
        report={"benchmark": {"id": 3}, "session_id": 9}, marks=[], events=[],
        session={"id": 9}, config={}, exported_at=datetime(2026, 10, 4, tzinfo=timezone.utc),
    )
    with ZipFile(BytesIO(build_benchmark_export(**arguments, trace=trace))) as zipped:
        assert zipped.read("benchmark-trace.jsonl") == trace
        manifest = json.loads(zipped.read("manifest.json"))
        assert manifest["trace"]["available"] is True
        assert manifest["trace"]["bytes"] == len(trace)
        assert manifest["files"]["benchmark-trace.jsonl"]["sha256"] == sha256(trace).hexdigest()
    for reason in ("not_found", "too_large", "timeout", "service_unavailable", "http_error_503"):
        with ZipFile(BytesIO(build_benchmark_export(**arguments, trace_reason=reason))) as zipped:
            manifest = json.loads(zipped.read("manifest.json"))
            assert manifest["trace"]["available"] is False
            assert manifest["trace"]["reason"] == reason
            assert manifest["trace"]["bytes"] == 0
            assert "benchmark-trace.jsonl" not in zipped.namelist()
    with ZipFile(BytesIO(build_benchmark_export(**arguments, trace=b""))) as zipped:
        assert json.loads(zipped.read("manifest.json"))["trace"]["reason"] == "empty"


def test_v0556_diagnostics_trace_bound_stops_stream_before_later_chunks() -> None:
    from app.benchmarking import BenchmarkTraceTooLarge, read_benchmark_trace_chunks

    read_chunks = []

    def chunks():
        for chunk in (b"123", b"456", b"must not be read"):
            read_chunks.append(chunk)
            yield chunk

    try:
        read_benchmark_trace_chunks(chunks(), max_bytes=5)
    except BenchmarkTraceTooLarge:
        pass
    else:
        raise AssertionError("An oversized trace must be rejected, not silently truncated")
    assert read_chunks == [b"123", b"456"]
    assert read_benchmark_trace_chunks((b"12", b"345"), max_bytes=5) == b"12345"


def test_v0556_diagnostics_source_identity_redacts_remote_credentials_and_local_directories() -> None:
    from app.benchmarking import benchmark_source_identity

    assert benchmark_source_identity("rtsp://user:pwd@[2001:db8::1]:554/live?password=secret#fragment") == "rtsp://[2001:db8::1]:554/live"
    assert benchmark_source_identity("https://media.local/clips/clip1.mp4?sig=private") == "https://media.local/clips/clip1.mp4"
    assert benchmark_source_identity(r"D:\User\Nhiên\Videos\clip1.mp4") == "clip1.mp4"
    assert benchmark_source_identity("/data/videos/clip1.mp4") == "clip1.mp4"
    assert benchmark_source_identity("rtsp://admin:pwd@camera:invalid/live") == "[source omitted]"
    assert benchmark_source_identity(None) is None
