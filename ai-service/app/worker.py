from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import httpx

from app.counting import CountingLine, LineCrossingCounter
from app.schemas import PipelineStart

VEHICLE_CLASSES = {"bicycle", "car", "motorcycle", "bus", "truck"}


class PipelineWorker(threading.Thread):
    def __init__(self, payload: PipelineStart, state, on_finished: Callable[[int], None]) -> None:
        super().__init__(daemon=True, name=f"camera-{payload.camera_id}")
        self.payload = payload
        self.state = state
        self.on_finished = on_finished
        self._stop_event = threading.Event()
        self._jpeg_lock = threading.Lock()
        self._latest_jpeg: bytes | None = None
        self.backend_url = os.getenv("BACKEND_INTERNAL_URL", "http://backend:8000/api/internal")
        self.shared_token = os.getenv("AI_SHARED_TOKEN", "TrafficAI-Local-2026")
        self.model_name = payload.model_path or os.getenv("AI_MODEL_NAME", "yolo26n.pt")
        self.device = os.getenv("AI_DEVICE", "auto")
        self.snapshot_root = Path(os.getenv("SNAPSHOT_DIR", "/tmp/traffic-ai-snapshots"))

    @property
    def latest_jpeg(self) -> bytes | None:
        with self._jpeg_lock:
            return self._latest_jpeg

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        cap = None
        started = time.perf_counter()
        try:
            import cv2
            import torch
            from ultralytics import YOLO

            device = self.device
            if device == "auto":
                device = 0 if torch.cuda.is_available() else "cpu"

            source = self._resolve_source()
            cap = cv2.VideoCapture(source)
            if not cap.isOpened():
                raise RuntimeError(f"Cannot open source: {self.payload.source_url}")

            model = YOLO(self.model_name)
            counter = LineCrossingCounter(
                CountingLine(
                    self.payload.line_x1,
                    self.payload.line_y1,
                    self.payload.line_x2,
                    self.payload.line_y2,
                )
            )
            self.state.status = "running"
            class_ids = self._vehicle_class_ids(model.names)

            while not self._stop_event.is_set():
                ok, frame = cap.read()
                if not ok:
                    self.state.status = "completed"
                    break

                results = model.track(
                    frame,
                    persist=True,
                    tracker="bytetrack.yaml",
                    conf=self.payload.confidence_threshold,
                    classes=class_ids,
                    device=device,
                    verbose=False,
                )
                result = results[0]
                height, width = frame.shape[:2]
                counts = {"in": 0, "out": 0}

                boxes = result.boxes
                if boxes is not None and boxes.id is not None:
                    xyxy = boxes.xyxy.cpu().tolist()
                    ids = boxes.id.int().cpu().tolist()
                    classes = boxes.cls.int().cpu().tolist()
                    confs = boxes.conf.cpu().tolist()
                    for rect, track_id, cls_id, confidence in zip(xyxy, ids, classes, confs):
                        x1, y1, x2, y2 = rect
                        center = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
                        label = str(result.names[int(cls_id)])
                        direction = counter.update(track_id, center, width, height)
                        self._draw_detection(cv2, frame, rect, track_id, label, confidence)
                        if direction:
                            counts[direction] += 1
                            self.state.total_count += 1
                            snapshot = self._save_snapshot(cv2, frame, track_id)
                            self._post_event(track_id, label, direction, float(confidence), snapshot)

                self._draw_overlay(cv2, frame, counter, counts)
                ok_jpeg, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
                if ok_jpeg:
                    with self._jpeg_lock:
                        self._latest_jpeg = encoded.tobytes()

                self.state.processed_frames += 1
                elapsed = max(time.perf_counter() - started, 0.001)
                self.state.fps = round(self.state.processed_frames / elapsed, 2)

            if self.state.status == "running":
                self.state.status = "stopped"
        except Exception as exc:
            self.state.status = "error"
            self.state.last_error = str(exc)
        finally:
            if cap is not None:
                cap.release()
            self._notify_finished()
            self.on_finished(self.payload.camera_id)

    def _resolve_source(self):
        if self.payload.source_type == "webcam":
            return int(self.payload.source_url)
        return self.payload.source_url

    @staticmethod
    def _vehicle_class_ids(names) -> list[int]:
        mapping = names.items() if isinstance(names, dict) else enumerate(names)
        return [int(idx) for idx, name in mapping if str(name) in VEHICLE_CLASSES]

    @staticmethod
    def _draw_detection(cv2, frame, rect, track_id: int, label: str, confidence: float) -> None:
        x1, y1, x2, y2 = [int(v) for v in rect]
        cv2.rectangle(frame, (x1, y1), (x2, y2), (60, 220, 120), 2)
        cv2.putText(frame, f"{label} #{track_id} {confidence:.2f}", (x1, max(18, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (60, 220, 120), 2)

    def _draw_overlay(self, cv2, frame, counter: LineCrossingCounter, counts: dict[str, int]) -> None:
        h, w = frame.shape[:2]
        a, b = counter.line.denormalize(w, h)
        cv2.line(frame, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), (0, 200, 255), 3)
        cv2.putText(frame, f"TOTAL {self.state.total_count} | FPS {self.state.fps:.1f}", (20, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 255), 2)
        if counts["in"] or counts["out"]:
            cv2.putText(frame, f"Crossing IN +{counts['in']} OUT +{counts['out']}", (20, 64), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 200, 255), 2)

    def _save_snapshot(self, cv2, frame, track_id: int) -> str | None:
        try:
            folder = self.snapshot_root / f"camera_{self.payload.camera_id}"
            folder.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            path = folder / f"{stamp}_track_{track_id}.jpg"
            cv2.imwrite(str(path), frame)
            return str(path.relative_to(self.snapshot_root)).replace("\\", "/")
        except Exception:
            return None

    def _post_event(self, track_id: int, label: str, direction: str, confidence: float, snapshot: str | None) -> None:
        payload = {
            "camera_id": self.payload.camera_id,
            "session_id": self.payload.session_id,
            "model_id": self.payload.model_id,
            "tracking_id": track_id,
            "vehicle_type": label if label in VEHICLE_CLASSES else "other",
            "direction": direction,
            "confidence": confidence,
            "snapshot_path": snapshot,
        }
        try:
            httpx.post(
                f"{self.backend_url}/events",
                json=payload,
                headers={"X-AI-Token": self.shared_token},
                timeout=3.0,
            ).raise_for_status()
        except Exception:
            pass

    def _notify_finished(self) -> None:
        try:
            httpx.post(
                f"{self.backend_url}/sessions/{self.payload.session_id}/finish",
                json={
                    "status": self.state.status,
                    "total_vehicles": self.state.total_count,
                    "average_fps": self.state.fps,
                    "last_error": self.state.last_error,
                },
                headers={"X-AI-Token": self.shared_token},
                timeout=3.0,
            ).raise_for_status()
        except Exception:
            pass
