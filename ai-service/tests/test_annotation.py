import json

import app.training as training
from app.annotation import accept_safe_annotations, list_annotations, parse_yolo_label, serialize_yolo_label


def test_yolo_annotation_roundtrip():
    text = '0 0.500000 0.400000 0.200000 0.100000\n4 0.250000 0.300000 0.150000 0.220000\n'
    boxes = parse_yolo_label(text)
    assert [b['class_name'] for b in boxes] == ['motorcycle', 'truck']
    assert serialize_yolo_label(boxes) == text


def test_invalid_annotation_rows_are_ignored():
    boxes = parse_yolo_label('99 0.5 0.5 0.2 0.2\n1 bad 0.5 0.2 0.2\n2 0.4 0.4 0.0 0.2\n')
    assert boxes == []


def test_smart_review_prioritizes_two_wheelers_and_bulk_accepts_safe_only(tmp_path, monkeypatch):
    dataset_root = tmp_path / 'datasets'
    monkeypatch.setattr(training, 'DATASET_ROOT', dataset_root)
    raw_images = dataset_root / 'demo' / 'raw' / 'images'
    raw_labels = dataset_root / 'demo' / 'raw' / 'labels'
    raw_images.mkdir(parents=True)
    raw_labels.mkdir(parents=True)
    for name in ('bike.jpg', 'car.jpg', 'empty.jpg'):
        (raw_images / name).write_bytes(b'fake')
    (raw_labels / 'bike.txt').write_text('1 0.5 0.5 0.2 0.2\n', encoding='utf-8')
    (raw_labels / 'car.txt').write_text('2 0.5 0.5 0.2 0.2\n', encoding='utf-8')
    (raw_labels / 'empty.txt').write_text('', encoding='utf-8')
    meta = {
        'bike.jpg': {'score': 50, 'reasons': ['Có nhãn bicycle'], 'safe_auto_accept': False, 'min_confidence': 0.95, 'mean_confidence': 0.95},
        'car.jpg': {'score': 0, 'reasons': ['Nhãn tương đối ổn định'], 'safe_auto_accept': True, 'min_confidence': 0.91, 'mean_confidence': 0.91},
        'empty.jpg': {'score': 55, 'reasons': ['Không phát hiện phương tiện'], 'safe_auto_accept': False, 'min_confidence': None, 'mean_confidence': None},
    }
    (dataset_root / 'demo' / 'raw' / 'auto_label_meta.json').write_text(json.dumps(meta, ensure_ascii=False), encoding='utf-8')

    priority = list_annotations('demo', review_mode='priority')
    assert [item['image_name'] for item in priority['items']] == ['empty.jpg', 'bike.jpg']
    assert priority['safe_auto_accept_images'] == 1

    accepted = accept_safe_annotations('demo', 0.70)
    assert accepted['accepted_images'] == 1
    review = json.loads((dataset_root / 'demo' / 'annotation_review.json').read_text(encoding='utf-8'))
    assert review['reviewed'] == ['car.jpg']
