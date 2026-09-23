from app.counting import CountingLine
from app.gate_roi import gate_roi_for_line


def test_gate_roi_focuses_horizontal_counting_area() -> None:
    roi = gate_roi_for_line(CountingLine(0.32, 0.59, 0.84, 0.59), 1000, 600, margin_ratio=0.20, min_span_ratio=0.50)
    assert roi.x1 <= 320
    assert roi.x2 >= 840
    assert roi.y1 < 354 < roi.y2
    assert roi.height >= 300
    assert roi.width <= 1000
