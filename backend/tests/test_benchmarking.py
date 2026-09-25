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


def rich_item(idx, time, direction="in", vehicle_type="motorcycle", tracking_id=None, crossing_method=None, confidence=0.9):
    return SimpleNamespace(
        id=idx,
        source_time_seconds=time,
        direction=direction,
        vehicle_type=vehicle_type,
        tracking_id=tracking_id,
        crossing_method=crossing_method,
        confidence=confidence,
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
