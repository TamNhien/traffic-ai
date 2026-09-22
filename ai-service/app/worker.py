from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import httpx

from app.classification import TrackLabelSmoother
from app.counting import CountingLine, LineCrossingCounter
from app.schemas import PipelineStart

VEHICLE_CLASSES = {"bicycle", "car", "motorcycle", "bus", "truck"}
HEAVY_VEHICLE_CLASSES = {"bus", "truck"}


class PipelineWorker(threading.Thread):
    def __init__(self, payload: PipelineStart, state, on_finished: Callable[[int], None]) -> None:
        super().__init__(daemon=True, name=f"camera-{payload.camera_id}")
        self.payload = payload
        self.state = state
        self.on_finished = on_finished
        self._stop_event = threading.Event()
        self._jpeg_lock = threading.Lock()
        self._latest_jpeg: bytes | None = None
        self._pending_events: list[dict] = []
        self._seen_track_ids: set[int] = set()
        self._labels = TrackLabelSmoother(history=int(os.getenv("AI_CLASS_HISTORY", "18")))
        self._refiner_model = None
        self.backend_url = os.getenv("BACKEND_INTERNAL_URL", "http://backend:8000/api/internal")
        self.shared_token = os.getenv("AI_SHARED_TOKEN", "TrafficAI-Local-2026")
        self.model_name = payload.model_path or os.getenv("AI_MODEL_NAME", "yolo26n.pt")
        self.device = os.getenv("AI_DEVICE", "auto")
        self.snapshot_root = Path(os.getenv("SNAPSHOT_DIR", "/tmp/traffic-ai-snapshots"))
        self.imgsz = int(os.getenv("AI_IMGSZ", "960"))
        self.process_max_width = int(os.getenv("AI_PROCESS_MAX_WIDTH", "1280"))
        self.jpeg_quality = int(os.getenv("AI_JPEG_QUALITY", "76"))
        self.heavy_refine = os.getenv("AI_HEAVY_REFINE", "1").strip().lower() not in {"0", "false", "no"}
        self.tracker_config = str(Path(__file__).with_name("bytetrack_traffic.yaml"))

    @property
    def latest_jpeg(self) -> bytes | None:
        with self._jpeg_lock:
            return self._latest_jpeg

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        cap = None
        loop_started = None
        try:
            import cv2
            import torch
            from ultralytics import YOLO

            cv2.setNumThreads(1)
            if torch.cuda.is_available():
                torch.backends.cudnn.benchmark = True

            device = self.device
            if device == "auto":
                device = 0 if torch.cuda.is_available() else "cpu"
            use_half = device != "cpu" and bool(torch.cuda.is_available())

            source = self._resolve_source()
            cap = cv2.VideoCapture(source)
            if self.payload.source_type == "rtsp":
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
            if not cap.isOpened():
                raise RuntimeError(f"Cannot open source: {self.payload.source_url}")

            model = YOLO(self.model_name)
            counter = LineCrossingCounter(
                CountingLine(
                    self.payload.line_x1,
                    self.payload.line_y1,
                    self.payload.line_x2,
                    self.payload.line_y2,
                ),
                segment_margin=0.08,
                dead_band_ratio=0.012,
                rearm_distance_ratio=0.045,
            )
            class_ids = self._vehicle_class_ids(model.names)
            if not class_ids:
                raise RuntimeError("YOLO model does not expose supported vehicle classes")
            heavy_ids = self._named_class_ids(model.names, HEAVY_VEHICLE_CLASSES)

            self.state.status = "running"
            self.state.model_name = self.model_name
            self.state.imgsz = self.imgsz
            self.state.half_precision = use_half
            loop_started = time.perf_counter()

            while not self._stop_event.is_set():
                ok, source_frame = cap.read()
                if not ok:
                    self.state.status = "completed"
                    break

                frame = self._resize_for_processing(cv2, source_frame)
                infer_started = time.perf_counter()
                results = model.track(
                    frame,
                    persist=True,
                    tracker=self.tracker_config,
                    conf=self.payload.confidence_threshold,
                    classes=class_ids,
                    device=device,
                    imgsz=self.imgsz,
                    half=use_half,
                    verbose=False,
                )
                self.state.inference_ms = round((time.perf_counter() - infer_started) * 1000.0, 1)
                result = results[0]
                height, width = frame.shape[:2]
                self.state.frame_width = width
                self.state.frame_height = height

                boxes = result.boxes
                if boxes is not None and boxes.id is not None:
                    xyxy = boxes.xyxy.cpu().tolist()
                    ids = boxes.id.int().cpu().tolist()
                    classes = boxes.cls.int().cpu().tolist()
                    confs = boxes.conf.cpu().tolist()
                    for rect, track_id_raw, cls_id, confidence in zip(xyxy, ids, classes, confs):
                        track_id = int(track_id_raw)
                        x1, y1, x2, y2 = rect
                        anchor = ((x1 + x2) / 2.0, y2)
                        current_label = str(result.names[int(cls_id)])
                        confidence_f = float(confidence)
                        self._seen_track_ids.add(track_id)
                        self._labels.update(track_id, current_label, confidence_f)
                        stable_label, class_certainty, class_hits = self._labels.stable_label(track_id, current_label)

                        direction = counter.update(track_id, anchor, width, height)
                        display_label = stable_label if class_hits >= 3 else current_label
                        self._draw_detection(
                            cv2,
                            frame,
                            rect,
                            track_id,
                            display_label,
                            confidence_f,
                            anchor,
                            class_certainty,
                        )

                        if direction:
                            event_label = display_label
                            event_confidence = confidence_f
                            if self.heavy_refine and (event_label in HEAVY_VEHICLE_CLASSES or current_label in HEAVY_VEHICLE_CLASSES):
                                refined = self._refine_heavy_label(
                                    YOLO,
                                    cv2,
                                    frame,
                                    rect,
                                    device,
                                    use_half,
                                    heavy_ids,
                                )
                                if refined is not None:
                                    refined_label, refined_conf = refined
                                    # A dedicated crop is higher resolution than the
                                    # full frame at the crossing point, so give a
                                    # confident refinement precedence over a one-frame
                                    # bus/truck flip from the detector.
                                    if refined_conf >= 0.28 or class_certainty < 0.72:
                                        event_label = refined_label
                                        event_confidence = max(event_confidence, refined_conf)

                            self.state.total_count += 1
                            self.state.in_count = counter.in_count
                            self.state.out_count = counter.out_count
                            snapshot = self._save_snapshot(cv2, frame, track_id)
                            event = self._event_payload(track_id, event_label, direction, event_confidence, snapshot)
                            if not self._deliver_event(event):
                                self._pending_events.append(event)

                self.state.detected_tracks = len(self._seen_track_ids)
                self._flush_pending_events(max_items=8)
                self._draw_overlay(cv2, frame, counter)
                ok_jpeg, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality])
                if ok_jpeg:
                    with self._jpeg_lock:
                        self._latest_jpeg = encoded.tobytes()

                self.state.processed_frames += 1
                elapsed = max(time.perf_counter() - (loop_started or time.perf_counter()), 0.001)
                self.state.fps = round(self.state.processed_frames / elapsed, 2)

            if self.state.status == "running":
                self.state.status = "stopped"
        except Exception as exc:
            self.state.status = "error"
            self.state.last_error = str(exc)
        finally:
            if cap is not None:
                cap.release()
            for _ in range(5):
                if not self._pending_events:
                    break
                self._flush_pending_events(max_items=100)
                if self._pending_events:
                    time.sleep(0.4)
            self._notify_finished()
            self.on_finished(self.payload.camera_id)

    def _resolve_source(self):
        if self.payload.source_type == "webcam":
            return int(self.payload.source_url)
        return self.payload.source_url

    def _resize_for_processing(self, cv2, frame):
        height, width = frame.shape[:2]
        if self.process_max_width <= 0 or width <= self.process_max_width:
            return frame
        scale = self.process_max_width / float(width)
        target = (self.process_max_width, max(2, int(round(height * scale))))
        return cv2.resize(frame, target, interpolation=cv2.INTER_AREA)

    @staticmethod
    def _vehicle_class_ids(names) -> list[int]:
        mapping = names.items() if isinstance(names, dict) else enumerate(names)
        return [int(idx) for idx, name in mapping if str(name) in VEHICLE_CLASSES]

    @staticmethod
    def _named_class_ids(names, labels: set[str]) -> list[int]:
        mapping = names.items() if isinstance(names, dict) else enumerate(names)
        return [int(idx) for idx, name in mapping if str(name) in labels]

    def _refine_heavy_label(self, YOLO, cv2, frame, rect, device, use_half: bool, heavy_ids: list[int]) -> tuple[str, float] | None:
        if not heavy_ids:
            return None
        try:
            h, w = frame.shape[:2]
            x1, y1, x2, y2 = rect
            pad_x = max(8, int((x2 - x1) * 0.12))
            pad_y = max(8, int((y2 - y1) * 0.12))
            ix1 = max(0, int(x1) - pad_x)
            iy1 = max(0, int(y1) - pad_y)
            ix2 = min(w, int(x2) + pad_x)
            iy2 = min(h, int(y2) + pad_y)
            crop = frame[iy1:iy2, ix1:ix2]
            if crop.size == 0 or crop.shape[0] < 32 or crop.shape[1] < 32:
                return None
            if self._refiner_model is None:
                self._refiner_model = YOLO(self.model_name)
            predictions = self._refiner_model.predict(
                crop,
                conf=0.10,
                classes=heavy_ids,
                device=device,
                imgsz=640,
                half=use_half,
                verbose=False,
            )
            if not predictions:
                return None
            boxes = predictions[0].boxes
            if boxes is None or len(boxes) == 0:
                return None
            confs = boxes.conf.cpu().tolist()
            classes = boxes.cls.int().cpu().tolist()
            best_index = max(range(len(confs)), key=lambda idx: confs[idx])
            label = str(predictions[0].names[int(classes[best_index])])
            if label not in HEAVY_VEHICLE_CLASSES:
                return None
            return label, float(confs[best_index])
        except Exception:
            return None

    @staticmethod
    def _draw_detection(cv2, frame, rect, track_id: int, label: str, confidence: float, anchor, class_certainty: float) -> None:
        x1, y1, x2, y2 = [int(v) for v in rect]
        cv2.rectangle(frame, (x1, y1), (x2, y2), (60, 220, 120), 2)
        cv2.circle(frame, (int(anchor[0]), int(anchor[1])), 5, (255, 220, 0), -1)
        text = f"{label} #{track_id} {confidence:.2f}"
        if class_certainty > 0:
            text += f" s{class_certainty:.2f}"
        cv2.putText(frame, text, (x1, max(18, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (60, 220, 120), 2)

    def _draw_overlay(self, cv2, frame, counter: LineCrossingCounter) -> None:
        h, w = frame.shape[:2]
        a, b = counter.line.denormalize(w, h)
        cv2.line(frame, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), (0, 200, 255), 3)
        cv2.circle(frame, (int(a[0]), int(a[1])), 7, (0, 200, 255), -1)
        cv2.circle(frame, (int(b[0]), int(b[1])), 7, (0, 200, 255), -1)
        dx = b[0] - a[0]
        dy = b[1] - a[1]
        length = max((dx * dx + dy * dy) ** 0.5, 1.0)
        nx, ny = -dy / length, dx / length
        mx, my = (a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0
        offset = max(28.0, h * 0.035)
        cv2.putText(frame, "IN", (int(mx + nx * offset), int(my + ny * offset)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 160), 2)
        cv2.putText(frame, "OUT", (int(mx - nx * offset), int(my - ny * offset)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (80, 180, 255), 2)
        cv2.putText(
            frame,
            f"TOTAL {self.state.total_count} | IN {counter.in_count} | OUT {counter.out_count} | FPS {self.state.fps:.1f} | {self.state.inference_ms:.0f}ms",
            (20, 32),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.66,
            (0, 200, 255),
            2,
        )
        if self._pending_events:
            cv2.putText(frame, f"DB PENDING {len(self._pending_events)}", (20, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 165, 255), 2)

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

    def _event_payload(self, track_id: int, label: str, direction: str, confidence: float, snapshot: str | None) -> dict:
        return {
            "camera_id": self.payload.camera_id,
            "session_id": self.payload.session_id,
            "model_id": self.payload.model_id,
            "tracking_id": track_id,
            "vehicle_type": label if label in VEHICLE_CLASSES else "other",
            "direction": direction,
            "confidence": confidence,
            "snapshot_path": snapshot,
        }

    def _deliver_event(self, payload: dict) -> bool:
        for attempt in range(1, 4):
            try:
                response = httpx.post(
                    f"{self.backend_url}/events",
                    json=payload,
                    headers={"X-AI-Token": self.shared_token},
                    timeout=4.0,
                )
                response.raise_for_status()
                self.state.delivered_events += 1
                self.state.pending_events = len(self._pending_events)
                if self.state.last_error and self.state.last_error.startswith("Event delivery attempt"):
                    self.state.last_error = None
                return True
            except Exception as exc:
                self.state.delivery_failures += 1
                self.state.last_error = f"Event delivery attempt {attempt} failed: {exc}"
                if attempt < 3:
                    time.sleep(0.2 * attempt)
        return False

    def _flush_pending_events(self, max_items: int) -> None:
        if not self._pending_events:
            self.state.pending_events = 0
            return
        remaining: list[dict] = []
        for index, event in enumerate(self._pending_events):
            if index >= max_items or not self._deliver_event(event):
                remaining.append(event)
        self._pending_events = remaining
        self.state.pending_events = len(remaining)

    def _notify_finished(self) -> None:
        payload = {
            "status": self.state.status,
            "total_vehicles": self.state.total_count,
            "average_fps": self.state.fps,
            "last_error": self.state.last_error,
        }
        for attempt in range(1, 7):
            try:
                response = httpx.post(
                    f"{self.backend_url}/sessions/{self.payload.session_id}/finish",
                    json=payload,
                    headers={"X-AI-Token": self.shared_token},
                    timeout=4.0,
                )
                response.raise_for_status()
                return
            except Exception as exc:
                self.state.last_error = f"Session finish notification attempt {attempt} failed: {exc}"
                if attempt < 6:
                    time.sleep(0.35 * attempt)
