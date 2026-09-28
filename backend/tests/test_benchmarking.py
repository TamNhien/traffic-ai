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
