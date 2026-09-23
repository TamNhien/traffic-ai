from app.annotation import parse_yolo_label, serialize_yolo_label


def test_yolo_annotation_roundtrip():
    text = '0 0.500000 0.400000 0.200000 0.100000\n4 0.250000 0.300000 0.150000 0.220000\n'
    boxes = parse_yolo_label(text)
    assert [b['class_name'] for b in boxes] == ['motorcycle', 'truck']
    assert serialize_yolo_label(boxes) == text


def test_invalid_annotation_rows_are_ignored():
    boxes = parse_yolo_label('99 0.5 0.5 0.2 0.2\n1 bad 0.5 0.2 0.2\n2 0.4 0.4 0.0 0.2\n')
    assert boxes == []
