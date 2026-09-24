from app.dedup import box_iou, keep_single_heavy_vehicle, single_heavy_vehicle_plan


def test_box_iou_for_same_box_is_one() -> None:
    assert box_iou((10, 10, 110, 110), (10, 10, 110, 110)) == 1.0


def test_overlapping_bus_truck_keeps_one_physical_vehicle_and_aliases_loser() -> None:
    rects = [(100, 100, 320, 300), (108, 105, 318, 302), (500, 100, 620, 240)]
    labels = ["bus", "truck", "car"]
    confidences = [0.62, 0.81, 0.74]
    keep, aliases, suppressed = single_heavy_vehicle_plan(rects, labels, confidences, 0.68)
    assert suppressed == 1
    assert keep == [1, 2]
    assert aliases == {1: [0]}


def test_distinct_bus_and_truck_are_not_merged() -> None:
    rects = [(100, 100, 250, 280), (280, 100, 430, 280)]
    labels = ["bus", "truck"]
    confidences = [0.8, 0.79]
    keep, suppressed = keep_single_heavy_vehicle(rects, labels, confidences, 0.68)
    assert suppressed == 0
    assert keep == [0, 1]


def test_same_class_heavy_boxes_are_not_modified_by_cross_class_guard() -> None:
    rects = [(100, 100, 250, 280), (105, 105, 245, 275)]
    labels = ["truck", "truck"]
    confidences = [0.8, 0.7]
    keep, suppressed = keep_single_heavy_vehicle(rects, labels, confidences, 0.68)
    assert suppressed == 0
    assert keep == [0, 1]
