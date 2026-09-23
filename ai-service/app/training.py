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
MODEL_ROOT = Path(os.getenv("AI_MODEL_ROOT", "/data/models"))
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




def _candidate_changed_enough(changed_ratio: float, min_change_ratio: float) -> bool:
    """Return True when a sampled frame is visually different enough to keep.

    This helper is intentionally dependency-free so unit tests can verify the
    smart-frame policy without importing OpenCV/Numpy.
    """
    return float(changed_ratio) >= max(0.0, float(min_change_ratio))


def _review_priority(boxes: list[dict[str, Any]]) -> dict[str, Any]:
    """Score pseudo-labels so humans review risky frames first.

    Motorcycle/bicycle confusion is the primary failure mode for this project,
    so any two-wheel prediction is deliberately kept out of bulk auto-accept.
    Empty detections are also review candidates because they may hide a miss.
    """
    if not boxes:
        return {
            "score": 55,
            "reasons": ["Không phát hiện phương tiện"],
            "safe_auto_accept": False,
            "min_confidence": None,
            "mean_confidence": None,
        }
    confidences = [max(0.0, min(1.0, float(b.get("confidence", 0.0)))) for b in boxes]
    class_ids = [int(b.get("class_id", -1)) for b in boxes]
    score = 0
    reasons: list[str] = []
    min_conf = min(confidences)
    mean_conf = sum(confidences) / max(1, len(confidences))
    has_two_wheeler = any(cid in {0, 1} for cid in class_ids)
    has_bicycle = 1 in class_ids
    if has_two_wheeler:
        score += 35
        reasons.append("Có xe máy/xe đạp cần kiểm tra kỹ")
    if has_bicycle:
        score += 15
        reasons.append("Có nhãn bicycle")
    if min_conf < 0.45:
        score += 35
        reasons.append("Confidence thấp")
    elif min_conf < 0.60:
        score += 20
        reasons.append("Confidence trung bình")
    if len(boxes) >= 8:
        score += 25
        reasons.append("Khung hình rất đông xe")
    elif len(boxes) >= 5:
        score += 15
        reasons.append("Khung hình đông xe")
    safe_auto_accept = (
        not has_two_wheeler
        and len(boxes) <= 4
        and min_conf >= 0.70
        and mean_conf >= 0.78
    )
    return {
        "score": min(100, score),
        "reasons": reasons or ["Nhãn tương đối ổn định"],
        "safe_auto_accept": safe_auto_accept,
        "min_confidence": round(min_conf, 4),
        "mean_confidence": round(mean_conf, 4),
    }
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


def extract_frames(
    source_path: Path,
    slug: str,
    every_n_frames: int = 15,
    max_images: int = 600,
    smart_dedupe: bool = True,
    min_change_ratio: float = 0.008,
) -> dict[str, Any]:
    # OpenCV là dependency runtime nặng. Import tại nơi sử dụng để các unit test
    # thuần logic không phải cài OpenCV.
    import cv2
    if every_n_frames < 1:
        raise ValueError("every_n_frames phải >= 1")
    if max_images < 10:
        raise ValueError("max_images phải >= 10")
    if not 0.0 <= min_change_ratio <= 1.0:
        raise ValueError("min_change_ratio phải nằm trong 0..1")
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
    sampled = 0
    skipped_similar = 0
    frame_index = 0
    last_signature = None
    try:
        while written < max_images:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_index % every_n_frames == 0:
                sampled += 1
                keep = True
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                signature = cv2.resize(gray, (160, 90), interpolation=cv2.INTER_AREA)
                if smart_dedupe and last_signature is not None:
                    diff = cv2.absdiff(signature, last_signature)
                    _, changed = cv2.threshold(diff, 12, 255, cv2.THRESH_BINARY)
                    changed_ratio = float(cv2.countNonZero(changed)) / float(changed.size or 1)
                    keep = _candidate_changed_enough(changed_ratio, min_change_ratio)
                    if not keep:
                        skipped_similar += 1
                if keep:
                    name = f"frame_{frame_index:08d}.jpg"
                    if not cv2.imwrite(str(raw_images / name), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 92]):
                        raise RuntimeError(f"Không ghi được frame {name}")
                    written += 1
                    last_signature = signature
            frame_index += 1
    finally:
        cap.release()
    meta = {
        "slug": safe_slug(slug),
        "source_path": str(source_path),
        "source_frames": source_frames,
        "source_fps": source_fps,
        "sample_every_n_frames": every_n_frames,
        "max_images": max_images,
        "smart_dedupe": bool(smart_dedupe),
        "min_change_ratio": float(min_change_ratio),
        "sampled_candidates": sampled,
        "skipped_similar": skipped_similar,
        "image_count": written,
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
    priority_images = 0
    safe_auto_accept_images = 0
    review_meta: dict[str, Any] = {}
    for image in images:
        results = model.predict(str(image), conf=confidence, verbose=False)
        lines: list[str] = []
        box_meta: list[dict[str, Any]] = []
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
                    conf_value = float(box.conf[0].item()) if getattr(box, "conf", None) is not None else 0.0
                    lines.append(f"{mapped} " + " ".join(f"{float(v):.6f}" for v in xywhn))
                    box_meta.append({
                        "class_id": mapped,
                        "class_name": VEHICLE_CLASSES[mapped],
                        "confidence": round(conf_value, 4),
                    })
        (label_dir / f"{image.stem}.txt").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        review = _review_priority(box_meta)
        if review["score"] >= 35:
            priority_images += 1
        if review["safe_auto_accept"]:
            safe_auto_accept_images += 1
        review_meta[image.name] = {
            "box_count": len(box_meta),
            "classes": sorted({b["class_name"] for b in box_meta}),
            **review,
        }
        if lines:
            labeled_images += 1
            boxes_total += len(lines)
    meta_path = target / "raw" / "auto_label_meta.json"
    meta_path.write_text(json.dumps(review_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "image_count": len(images),
        "labeled_images": labeled_images,
        "box_count": boxes_total,
        "classes": VEHICLE_CLASSES,
        "priority_images": priority_images,
        "safe_auto_accept_images": safe_auto_accept_images,
    }


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
    review_meta: dict[str, Any] = {}
    meta_path = target / "raw" / "auto_label_meta.json"
    if meta_path.exists():
        try:
            loaded = json.loads(meta_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                review_meta = loaded
        except Exception:
            review_meta = {}
    priority_images = sum(1 for v in review_meta.values() if isinstance(v, dict) and int(v.get("score", 0)) >= 35)
    safe_auto_accept_images = sum(1 for v in review_meta.values() if isinstance(v, dict) and bool(v.get("safe_auto_accept")))
    return {
        "image_count": len(images),
        "labeled_images": labeled_images,
        "label_count": len(labels),
        "box_count": boxes,
        "per_class": per_class,
        "priority_images": priority_images,
        "safe_auto_accept_images": safe_auto_accept_images,
    }


def reset_dataset_labels(slug: str) -> dict[str, Any]:
    """Keep extracted images but remove pseudo labels/review/splits for a clean relabel."""
    target = dataset_dir(slug)
    if not target.exists():
        raise FileNotFoundError(slug)
    raw_images = target / "raw" / "images"
    image_count = len(list(raw_images.glob("*.jpg"))) if raw_images.exists() else 0
    for path in [target / "raw" / "labels", target / "images", target / "labels"]:
        if path.exists():
            shutil.rmtree(path)
    (target / "raw" / "labels").mkdir(parents=True, exist_ok=True)
    for path in [target / "dataset.yaml", target / "annotation_review.json", target / "raw" / "auto_label_meta.json"]:
        if path.exists():
            path.unlink()
    return {"slug": safe_slug(slug), "image_count": image_count, "status": "extracted"}


def purge_dataset(slug: str, run_ids: list[int] | None = None, purge_training_runs: bool = True) -> dict[str, Any]:
    """Delete dataset files and optional run folders, but never exported models in /data/models."""
    target = dataset_dir(slug)
    removed_dataset = False
    if target.exists():
        shutil.rmtree(target)
        removed_dataset = True
    removed_runs: list[int] = []
    if purge_training_runs:
        for raw_id in run_ids or []:
            run_id = int(raw_id)
            if run_id < 1:
                continue
            run_dir = (TRAINING_ROOT / f"run-{run_id}").resolve()
            root = TRAINING_ROOT.resolve()
            if root != run_dir and root not in run_dir.parents:
                continue
            if run_dir.exists():
                shutil.rmtree(run_dir)
                removed_runs.append(run_id)
    return {
        "slug": safe_slug(slug),
        "removed_dataset": removed_dataset,
        "removed_training_runs": removed_runs,
        "exported_models_preserved": True,
    }


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
            exported = MODEL_ROOT / f"traffic-ai-v059-run-{state.run_id}-best.pt"
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
