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
    assert result["per_class"]["truck"]["ground_truth"] == 1
    assert result["per_class"]["bus"]["ai"] == 1


def test_benchmark_tolerance_blocks_far_event() -> None:
    result = match_crossings([item(1, 10.0)], [item(11, 10.9)], 0.50)
    assert result["matched"] == 0
    assert result["missed"] == 1
    assert result["false_positives"] == 1
