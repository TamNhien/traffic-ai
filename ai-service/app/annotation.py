from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.training import VEHICLE_CLASSES, dataset_dir

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}


def _safe_image_name(value: str) -> str:
    name = Path(value).name
    if name != value or not name or Path(name).suffix.lower() not in IMAGE_EXTENSIONS:
        raise ValueError('Tên ảnh annotation không hợp lệ.')
    return name


def _review_path(slug: str) -> Path:
    return dataset_dir(slug) / 'annotation_review.json'


def _load_review(slug: str) -> dict[str, set[str]]:
    path = _review_path(slug)
    if not path.exists():
        return {'reviewed': set(), 'difficult': set()}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        data = {}
    return {
        'reviewed': set(str(v) for v in data.get('reviewed', [])),
        'difficult': set(str(v) for v in data.get('difficult', [])),
    }


def _save_review(slug: str, review: dict[str, set[str]]) -> None:
    path = _review_path(slug)
    payload = {
        'reviewed': sorted(review.get('reviewed', set())),
        'difficult': sorted(review.get('difficult', set())),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def parse_yolo_label(text: str) -> list[dict[str, Any]]:
    boxes: list[dict[str, Any]] = []
    for line in text.splitlines():
        row = line.strip()
        if not row:
            continue
        parts = row.split()
        if len(parts) != 5:
            continue
        try:
            class_id = int(parts[0])
            x, y, w, h = [float(v) for v in parts[1:]]
        except Exception:
            continue
        if class_id < 0 or class_id >= len(VEHICLE_CLASSES):
            continue
        x = min(1.0, max(0.0, x))
        y = min(1.0, max(0.0, y))
        w = min(1.0, max(0.0, w))
        h = min(1.0, max(0.0, h))
        if w <= 0 or h <= 0:
            continue
        boxes.append({
            'class_id': class_id,
            'class_name': VEHICLE_CLASSES[class_id],
            'x': x, 'y': y, 'w': w, 'h': h,
        })
    return boxes


def serialize_yolo_label(boxes: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for box in boxes:
        class_id = int(box.get('class_id', -1))
        if class_id < 0 or class_id >= len(VEHICLE_CLASSES):
            raise ValueError('class_id annotation không hợp lệ.')
        values = [float(box.get(k, 0)) for k in ('x', 'y', 'w', 'h')]
        x, y, w, h = values
        if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1):
            raise ValueError('Bounding box phải dùng tọa độ YOLO chuẩn hóa 0..1.')
        rows.append(f"{class_id} {x:.6f} {y:.6f} {w:.6f} {h:.6f}")
    return '\n'.join(rows) + ('\n' if rows else '')


def list_annotations(slug: str, offset: int = 0, limit: int = 200) -> dict[str, Any]:
    target = dataset_dir(slug)
    image_dir = target / 'raw' / 'images'
    label_dir = target / 'raw' / 'labels'
    images = sorted([p for p in image_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS]) if image_dir.exists() else []
    review = _load_review(slug)
    per_class = {name: 0 for name in VEHICLE_CLASSES}
    items: list[dict[str, Any]] = []
    for image in images:
        label = label_dir / f'{image.stem}.txt'
        boxes = parse_yolo_label(label.read_text(encoding='utf-8')) if label.exists() else []
        for box in boxes:
            per_class[box['class_name']] += 1
        items.append({
            'image_name': image.name,
            'box_count': len(boxes),
            'reviewed': image.name in review['reviewed'],
            'difficult': image.name in review['difficult'],
        })
    counts = [v for v in per_class.values() if v > 0]
    imbalance_ratio = round(max(counts) / min(counts), 2) if len(counts) >= 2 else None
    sliced = items[max(0, offset):max(0, offset) + max(1, min(limit, 1000))]
    return {
        'slug': slug,
        'total': len(items),
        'offset': max(0, offset),
        'limit': max(1, min(limit, 1000)),
        'reviewed_images': len(review['reviewed'] & {p.name for p in images}),
        'difficult_images': len(review['difficult'] & {p.name for p in images}),
        'per_class': per_class,
        'imbalance_ratio': imbalance_ratio,
        'items': sliced,
        'classes': VEHICLE_CLASSES,
    }


def get_annotation(slug: str, image_name: str) -> dict[str, Any]:
    name = _safe_image_name(image_name)
    target = dataset_dir(slug)
    image = target / 'raw' / 'images' / name
    if not image.exists():
        raise FileNotFoundError(name)
    label = target / 'raw' / 'labels' / f'{image.stem}.txt'
    boxes = parse_yolo_label(label.read_text(encoding='utf-8')) if label.exists() else []
    review = _load_review(slug)
    return {
        'slug': slug,
        'image_name': name,
        'boxes': boxes,
        'reviewed': name in review['reviewed'],
        'difficult': name in review['difficult'],
        'classes': VEHICLE_CLASSES,
    }


def get_annotation_image(slug: str, image_name: str) -> Path:
    name = _safe_image_name(image_name)
    image = dataset_dir(slug) / 'raw' / 'images' / name
    if not image.exists() or not image.is_file():
        raise FileNotFoundError(name)
    return image


def save_annotation(slug: str, image_name: str, boxes: list[dict[str, Any]], reviewed: bool, difficult: bool) -> dict[str, Any]:
    name = _safe_image_name(image_name)
    target = dataset_dir(slug)
    image = target / 'raw' / 'images' / name
    if not image.exists():
        raise FileNotFoundError(name)
    label_dir = target / 'raw' / 'labels'
    label_dir.mkdir(parents=True, exist_ok=True)
    label_path = label_dir / f'{image.stem}.txt'
    label_path.write_text(serialize_yolo_label(boxes), encoding='utf-8')
    review = _load_review(slug)
    if reviewed:
        review['reviewed'].add(name)
    else:
        review['reviewed'].discard(name)
    if difficult:
        review['difficult'].add(name)
    else:
        review['difficult'].discard(name)
    _save_review(slug, review)
    result = get_annotation(slug, name)
    summary = list_annotations(slug, 0, 1)
    result['reviewed_images'] = summary['reviewed_images']
    result['difficult_images'] = summary['difficult_images']
    result['per_class'] = summary['per_class']
    result['imbalance_ratio'] = summary['imbalance_ratio']
    return result
