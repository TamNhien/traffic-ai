from app.counting import CountingLine
from app.gate_roi import gate_roi_for_line


def test_gate_roi_focuses_horizontal_counting_area() -> None:
    roi = gate_roi_for_line(CountingLine(0.32, 0.59, 0.84, 0.59), 1000, 600, margin_ratio=0.20, min_span_ratio=0.50)
    assert roi.x1 <= 320
    assert roi.x2 >= 840
    assert roi.y1 < 354 < roi.y2
    assert 150 <= roi.height < 300
    assert roi.width <= 1000


def test_gate_roi_does_not_expand_far_beyond_line_endpoints() -> None:
    roi = gate_roi_for_line(CountingLine(0.32, 0.59, 0.84, 0.59), 1000, 600, margin_ratio=0.16, min_span_ratio=0.50, endpoint_margin_ratio=0.035)
    assert roi.x1 >= 250
    assert roi.x2 <= 910
    assert roi.width < 700


def test_road_zone_roi_tracks_whole_drivable_area_without_full_frame() -> None:
    from app.counting import RoadZone
    from app.gate_roi import road_zone_roi

    zone = RoadZone(0.20, 0.15, 0.80, 0.15, 0.92, 0.95, 0.08, 0.95)
    roi = road_zone_roi(zone, 1000, 600, margin_ratio=0.02)
    assert roi.x1 <= 80
    assert roi.x2 >= 920
    assert roi.y1 <= 90
    assert roi.y2 >= 570
    assert roi.width < 1000
    assert roi.height < 600
