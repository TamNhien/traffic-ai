from __future__ import annotations

import json
import os
import random
import re
import shutil
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


VEHICLE_CLASSES = ["motorcycle", "bicycle", "car", "bus", "truck"]
COCO_TO_DATASET = {3: 0, 1: 1, 2: 2, 5: 3, 7: 4}

DATASET_ROOT = Path(os.getenv("AI_DATASET_ROOT", "/data/datasets"))
TRAINING_ROOT = Path(os.getenv("AI_TRAINING_ROOT", "/data/training-runs"))
MODEL_ROOT = Path("/data/models")
DATASET_ROOT.mkdir(parents=True, exist_ok=True)
TRAINING_ROOT.mkdir(parents=True, exist_ok=True)
MODEL_ROOT.mkdir(parents=True, exist_ok=True)


def safe_slug(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9_-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-_")
    if not value:
        raise ValueError("Tên dataset không tạo được slug hợp lệ.")
    return value[:80]


def dataset_dir(slug: str) -> Path:
    root = DATASET_ROOT.resolve()
    candidate = (root / safe_slug(slug)).resolve()
    if root != candidate and root not in candidate.parents:
        raise ValueError("Dataset path không hợp lệ.")
    return candidate


def split_items(items: list[str], train_ratio: float, val_ratio: float, seed: int) -> dict[str, list[str]]:
    if not 0.5 <= train_ratio < 1.0:
        raise ValueError("train_ratio phải từ 0.5 đến dưới 1.0")
    if not 0.0 < val_ratio < 0.5 or train_ratio + val_ratio >= 1.0:
        raise ValueError("val_ratio không hợp lệ")
    values = list(items)
    random.Random(seed).shuffle(values)
    n = len(values)
    train_end = int(n * train_ratio)
    val_end = train_end + int(n * val_ratio)
    return {"train": values[:train_end], "val": values[train_end:val_end], "test": values[val_end:]}


def extract_frames(source_path: Path, slug: str, every_n_frames: int = 10, max_images: int = 1200) -> dict[str, Any]:
    # OpenCV là dependency runtime nặng. Import tại nơi sử dụng để các unit test
    # thuần logic (health/source metadata/split dataset) không phải cài OpenCV.
    import cv2
    if every_n_frames < 1:
        raise ValueError("every_n_frames phải >= 1")
    target = dataset_dir(slug)
    raw_images = target / "raw" / "images"
    raw_labels = target / "raw" / "labels"
    raw_images.mkdir(parents=True, exist_ok=True)
    raw_labels.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(source_path))
    if not cap.isOpened():
        raise ValueError(f"Không mở được video: {source_path}")
    source_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    source_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    written = 0
    frame_index = 0
    try:
        while written < max_images:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_index % every_n_frames == 0:
                name = f"frame_{frame_index:08d}.jpg"
                if not cv2.imwrite(str(raw_images / name), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 92]):
                    raise RuntimeError(f"Không ghi được frame {name}")
                written += 1
            frame_index += 1
    finally:
        cap.release()
    meta = {
        "slug": safe_slug(slug), "source_path": str(source_path), "source_frames": source_frames,
        "source_fps": source_fps, "sample_every_n_frames": every_n_frames, "image_count": written,
    }
    (target / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def auto_label(slug: str, model_path: str, confidence: float = 0.25) -> dict[str, Any]:
    from ultralytics import YOLO
    target = dataset_dir(slug)
    images = sorted((target / "raw" / "images").glob("*.jpg"))
    if not images:
        raise ValueError("Dataset chưa có frame để gán nhãn.")
    label_dir = target / "raw" / "labels"
    label_dir.mkdir(parents=True, exist_ok=True)
    model = YOLO(model_path)
    labeled_images = 0
    boxes_total = 0
    for image in images:
        results = model.predict(str(image), conf=confidence, verbose=False)
        lines: list[str] = []
        if results:
            result = results[0]
            boxes = getattr(result, "boxes", None)
            if boxes is not None:
                for box in boxes:
                    cls_id = int(box.cls[0].item())
                    mapped = COCO_TO_DATASET.get(cls_id)
                    if mapped is None:
                        continue
                    xywhn = box.xywhn[0].tolist()
                    lines.append(f"{mapped} " + " ".join(f"{float(v):.6f}" for v in xywhn))
        (label_dir / f"{image.stem}.txt").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        if lines:
            labeled_images += 1
            boxes_total += len(lines)
    return {"image_count": len(images), "labeled_images": labeled_images, "box_count": boxes_total, "classes": VEHICLE_CLASSES}


def dataset_stats(slug: str) -> dict[str, Any]:
    target = dataset_dir(slug)
    images = sorted((target / "raw" / "images").glob("*.jpg"))
    labels = {p.stem: p for p in (target / "raw" / "labels").glob("*.txt")}
    per_class = {name: 0 for name in VEHICLE_CLASSES}
    labeled_images = 0
    boxes = 0
    for image in images:
        label = labels.get(image.stem)
        if not label:
            continue
        rows = [line.strip() for line in label.read_text(encoding="utf-8").splitlines() if line.strip()]
        if rows:
            labeled_images += 1
        for row in rows:
            try:
                cid = int(row.split()[0])
                if 0 <= cid < len(VEHICLE_CLASSES):
                    per_class[VEHICLE_CLASSES[cid]] += 1
                    boxes += 1
            except Exception:
                continue
    return {"image_count": len(images), "labeled_images": labeled_images, "label_count": len(labels), "box_count": boxes, "per_class": per_class}


def prepare_dataset(slug: str, train_ratio: float = 0.70, val_ratio: float = 0.20, seed: int = 2026) -> dict[str, Any]:
    # PyYAML chỉ cần khi thực sự tạo dataset.yaml. Giữ import lazy để test harness
    # có thể import app.training bằng requirements-test.txt tối giản.
    import yaml
    target = dataset_dir(slug)
    raw_images = target / "raw" / "images"
    raw_labels = target / "raw" / "labels"
    images = sorted([p for p in raw_images.glob("*.jpg") if (raw_labels / f"{p.stem}.txt").exists()])
    if len(images) < 10:
        raise ValueError("Cần ít nhất 10 ảnh có file nhãn trước khi chuẩn bị train/val/test.")
    splits = split_items([p.name for p in images], train_ratio, val_ratio, seed)
    for split, names in splits.items():
        image_dir = target / "images" / split
        label_dir = target / "labels" / split
        if image_dir.exists(): shutil.rmtree(image_dir)
        if label_dir.exists(): shutil.rmtree(label_dir)
        image_dir.mkdir(parents=True, exist_ok=True)
        label_dir.mkdir(parents=True, exist_ok=True)
        for name in names:
            src_img = raw_images / name
            src_label = raw_labels / f"{Path(name).stem}.txt"
            shutil.copy2(src_img, image_dir / name)
            shutil.copy2(src_label, label_dir / src_label.name)
    data = {
        "path": str(target), "train": "images/train", "val": "images/val", "test": "images/test",
        "names": {i: name for i, name in enumerate(VEHICLE_CLASSES)},
    }
    yaml_path = target / "dataset.yaml"
    yaml_path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return {"dataset_yaml": str(yaml_path), "splits": {k: len(v) for k, v in splits.items()}, "classes": VEHICLE_CLASSES}


@dataclass(slots=True)
class TrainingState:
    run_id: int
    dataset_slug: str
    status: str = "queued"
    base_model: str = "yolo26s.pt"
    epochs: int = 80
    imgsz: int = 640
    batch: int = 8
    device: str = "auto"
    current_epoch: int = 0
    progress: float = 0.0
    precision: float | None = None
    recall: float | None = None
    map50: float | None = None
    map50_95: float | None = None
    best_model_path: str | None = None
    last_error: str | None = None
    started_at: float | None = None
    ended_at: float | None = None


class TrainingRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._states: dict[int, TrainingState] = {}
        self._threads: dict[int, threading.Thread] = {}

    def start(self, *, run_id: int, dataset_slug: str, base_model: str, epochs: int, imgsz: int, batch: int, device: str) -> dict[str, Any]:
        with self._lock:
            existing = self._threads.get(run_id)
            if existing and existing.is_alive():
                raise ValueError("Training run đang chạy.")
            state = TrainingState(run_id=run_id, dataset_slug=safe_slug(dataset_slug), base_model=base_model, epochs=epochs, imgsz=imgsz, batch=batch, device=device)
            thread = threading.Thread(target=self._run, args=(state,), daemon=True, name=f"traffic-ai-train-{run_id}")
            self._states[run_id] = state
            self._threads[run_id] = thread
            thread.start()
            return asdict(state)

    def _run(self, state: TrainingState) -> None:
        from ultralytics import YOLO
        state.status = "running"
        state.started_at = time.time()
        try:
            target = dataset_dir(state.dataset_slug)
            yaml_path = target / "dataset.yaml"
            if not yaml_path.exists():
                raise ValueError("Dataset chưa được prepare: thiếu dataset.yaml")
            device = state.device
            if device == "auto":
                try:
                    import torch
                    device = 0 if torch.cuda.is_available() else "cpu"
                except Exception:
                    device = "cpu"
            run_name = f"run-{state.run_id}"
            model = YOLO(state.base_model)

            def _on_epoch_end(trainer):
                try:
                    state.current_epoch = int(getattr(trainer, "epoch", 0)) + 1
                    state.progress = round(min(100.0, state.current_epoch * 100.0 / max(1, state.epochs)), 2)
                except Exception:
                    pass
            model.add_callback("on_train_epoch_end", _on_epoch_end)
            results = model.train(
                data=str(yaml_path), epochs=state.epochs, imgsz=state.imgsz, batch=state.batch,
                device=device, workers=int(os.getenv("AI_TRAIN_WORKERS", "4")),
                patience=int(os.getenv("AI_TRAIN_PATIENCE", "20")),
                cache=os.getenv("AI_TRAIN_CACHE", "false").lower() == "true",
                project=str(TRAINING_ROOT), name=run_name, exist_ok=True, verbose=False,
            )
            save_dir = Path(getattr(results, "save_dir", TRAINING_ROOT / run_name))
            best = save_dir / "weights" / "best.pt"
            if not best.exists():
                raise RuntimeError("Training hoàn tất nhưng không tìm thấy weights/best.pt")
            exported = MODEL_ROOT / f"traffic-ai-v050-run-{state.run_id}-best.pt"
            shutil.copy2(best, exported)
            metrics = getattr(results, "results_dict", {}) or {}
            state.precision = _metric(metrics, ["metrics/precision(B)", "precision"])
            state.recall = _metric(metrics, ["metrics/recall(B)", "recall"])
            state.map50 = _metric(metrics, ["metrics/mAP50(B)", "map50"])
            state.map50_95 = _metric(metrics, ["metrics/mAP50-95(B)", "map50-95"])
            state.best_model_path = str(exported)
            state.current_epoch = state.epochs
            state.progress = 100.0
            state.status = "completed"
        except Exception as exc:
            state.status = "failed"
            state.last_error = str(exc)
        finally:
            state.ended_at = time.time()

    def get(self, run_id: int) -> dict[str, Any]:
        with self._lock:
            state = self._states.get(run_id)
            if state is None:
                raise KeyError(run_id)
            return asdict(state)

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(v) for _, v in sorted(self._states.items(), reverse=True)]


def _metric(metrics: dict[str, Any], names: list[str]) -> float | None:
    for name in names:
        value = metrics.get(name)
        try:
            if value is not None:
                return float(value)
        except Exception:
            pass
    return None


training_registry = TrainingRegistry()
