from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import httpx2 as httpx

from app.async_tasks import EventDispatcher, LatestFrameEncoder
from app.classification import TrackLabelSmoother, VehicleClassPolicy
from app.counting import CountingLine, LineCrossingCounter
from app.gate_roi import gate_roi_for_line
from app.schemas import PipelineStart
from app.tracking import TrackContinuityResolver, motion_leading_anchor

VEHICLE_CLASSES = {"bicycle", "car", "motorcycle", "bus", "truck"}
REFINE_VEHICLE_CLASSES = {"bicycle", "car", "motorcycle", "bus", "truck"}
AMBIGUOUS_CLASSES = {"bicycle", "motorcycle", "car", "bus", "truck"}


class PipelineWorker(threading.Thread):
    def __init__(self, payload: PipelineStart, state, on_finished: Callable[[int], None]) -> None:
        super().__init__(daemon=True, name=f"camera-{payload.camera_id}")
        self.payload = payload
        self.state = state
        self.on_finished = on_finished
        self._stop_event = threading.Event()
        self._jpeg_condition = threading.Condition()
        self._latest_jpeg: bytes | None = None
        self._latest_jpeg_sequence = 0
        self._seen_track_ids: set[int] = set()
        self._labels = TrackLabelSmoother(history=int(os.getenv("AI_CLASS_HISTORY", "30")))
        self._class_policy = VehicleClassPolicy(
            bicycle_certainty=float(os.getenv("AI_BICYCLE_CERTAINTY", "0.76")),
            bicycle_hits=int(os.getenv("AI_BICYCLE_MIN_HITS", "4")),
        )
        self._refiner_model = None
        self._continuity = TrackContinuityResolver(
            max_gap_frames=int(os.getenv("AI_STITCH_MAX_GAP", "30")),
            max_distance_ratio=float(os.getenv("AI_STITCH_DISTANCE_RATIO", "0.14")),
        )
        self.backend_url = os.getenv("BACKEND_INTERNAL_URL", "http://backend:8000/api/internal")
        self.shared_token = os.getenv("AI_SHARED_TOKEN", "TrafficAI-Local-2026")
        self.model_name = payload.model_path or os.getenv("AI_MODEL_NAME", "yolo26s.pt")
        self.device = os.getenv("AI_DEVICE", "auto")
        self.snapshot_root = Path(os.getenv("SNAPSHOT_DIR", "/tmp/traffic-ai-snapshots"))
        self.imgsz = int(os.getenv("AI_IMGSZ", "640"))
        self.process_max_width = int(os.getenv("AI_PROCESS_MAX_WIDTH", "1440"))
        self.jpeg_quality = int(os.getenv("AI_JPEG_QUALITY", "70"))
        self.jpeg_every_n = max(1, int(os.getenv("AI_STREAM_EVERY_N", "2")))
        self.jpeg_max_width = int(os.getenv("AI_STREAM_MAX_WIDTH", "960"))
        self.gate_roi_enabled = os.getenv("AI_GATE_ROI", "1").strip().lower() not in {"0", "false", "no"}
        self.gate_roi_margin = float(os.getenv("AI_GATE_ROI_MARGIN", "0.22"))
        self.gate_roi_min_span = float(os.getenv("AI_GATE_ROI_MIN_SPAN", "0.52"))
        self.refine_at_crossing = os.getenv("AI_REFINE_AT_CROSSING", "1").strip().lower() not in {"0", "false", "no"}
        self.refine_model_name = os.getenv("AI_REFINE_MODEL_NAME", "yolo26m.pt")
        self.refine_imgsz = int(os.getenv("AI_REFINE_IMGSZ", "640"))
        self.warmup = os.getenv("AI_WARMUP", "1").strip().lower() not in {"0", "false", "no"}
        self.video_pace = os.getenv("AI_VIDEO_PACE", "1").strip().lower() not in {"0", "false", "no"}
        self.iou = float(os.getenv("AI_IOU", "0.55"))
        self.tracker_config = str(Path(__file__).with_name("bytetrack_traffic.yaml"))
        self._event_dispatcher = EventDispatcher(self.backend_url, self.shared_token, self.state)
        self._jpeg_encoder = LatestFrameEncoder(self._set_latest_jpeg, self.state, self.jpeg_quality, self.jpeg_max_width)

    @property
    def latest_jpeg(self) -> bytes | None:
        with self._jpeg_condition:
            return self._latest_jpeg

    def _set_latest_jpeg(self, payload: bytes) -> None:
        with self._jpeg_condition:
            self._latest_jpeg = payload
            self._latest_jpeg_sequence += 1
            self._jpeg_condition.notify_all()

    def wait_for_jpeg(self, after_sequence: int, timeout: float = 2.0) -> tuple[int, bytes | None]:
        with self._jpeg_condition:
            if self._latest_jpeg_sequence <= after_sequence and not self._stop_event.is_set():
                self._jpeg_condition.wait(timeout=max(0.05, timeout))
            if self._latest_jpeg_sequence <= after_sequence:
                return after_sequence, None
            return self._latest_jpeg_sequence, self._latest_jpeg

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        cap = None
        loop_started = None
        try:
            import cv2
            import numpy as np
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

            source_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
            source_frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0) if self.payload.source_type == "video" else 0
            self.state.source_fps = round(source_fps, 2) if source_fps > 0 else 0.0
            self.state.source_frame_count = source_frame_count
            if source_fps > 0 and source_frame_count > 0:
                self.state.source_duration_seconds = round(source_frame_count / source_fps, 3)
            self.state.frame_policy = "all-frames" if self.payload.source_type == "video" else "live-latest"
            self.state.status = "warming"

            model = YOLO(self.model_name)
            class_ids = self._vehicle_class_ids(model.names)
            if not class_ids:
                raise RuntimeError("YOLO model does not expose supported vehicle classes")

            refine_ids: list[int] = []
            if self.refine_at_crossing:
                # Load the secondary model before playback. The old runtime loaded
                # it on the first crossing, which visibly froze the clip.
                self._refiner_model = YOLO(self.refine_model_name)
                refine_ids = self._named_class_ids(self._refiner_model.names, REFINE_VEHICLE_CLASSES)

            if self.warmup:
                dummy = np.zeros((self.imgsz, self.imgsz, 3), dtype=np.uint8)
                model.predict(dummy, conf=0.15, classes=class_ids, device=device, imgsz=self.imgsz, half=use_half, verbose=False)
                if self._refiner_model is not None and refine_ids:
                    self._refiner_model.predict(
                        dummy,
                        conf=0.10,
                        classes=refine_ids,
                        device=device,
                        imgsz=min(self.refine_imgsz, self.imgsz),
                        half=use_half,
                        verbose=False,
                    )

            counter = LineCrossingCounter(
                CountingLine(self.payload.line_x1, self.payload.line_y1, self.payload.line_x2, self.payload.line_y2),
                segment_margin=0.07,
                dead_band_ratio=0.006,
                rearm_distance_ratio=0.028,
                history_gap_frames=int(os.getenv("AI_GATE_HISTORY_GAP", "30")),
                min_perpendicular_ratio=float(os.getenv("AI_GATE_MIN_NORMAL_RATIO", "0.12")),
            )

            self._event_dispatcher.start()
            self._jpeg_encoder.start()
            self.state.status = "running"
            self.state.model_name = self.model_name
            self.state.refine_model_name = self.refine_model_name if self._refiner_model is not None else None
            self.state.imgsz = self.imgsz
            self.state.half_precision = use_half
            self.state.gate_roi_enabled = self.gate_roi_enabled
            loop_started = time.perf_counter()

            while not self._stop_event.is_set():
                ok, source_frame = cap.read()
                if not ok:
                    self.state.status = "completed"
                    break

                frame = self._resize_for_processing(cv2, source_frame)
                height, width = frame.shape[:2]
                self.state.frame_width = width
                self.state.frame_height = height
                frame_index = self.state.processed_frames + 1

                roi = gate_roi_for_line(
                    counter.line,
                    width,
                    height,
                    margin_ratio=self.gate_roi_margin,
                    min_span_ratio=self.gate_roi_min_span,
                ) if self.gate_roi_enabled else None
                infer_frame = roi.crop(frame) if roi is not None else frame
                offset_x = roi.x1 if roi is not None else 0
                offset_y = roi.y1 if roi is not None else 0
                if roi is not None:
                    self.state.gate_roi = {"x1": roi.x1, "y1": roi.y1, "x2": roi.x2, "y2": roi.y2}

                infer_started = time.perf_counter()
                results = model.track(
                    infer_frame,
                    persist=True,
                    tracker=self.tracker_config,
                    conf=self.payload.confidence_threshold,
                    iou=self.iou,
                    classes=class_ids,
                    device=device,
                    imgsz=self.imgsz,
                    half=use_half,
                    verbose=False,
                )
                self.state.inference_ms = round((time.perf_counter() - infer_started) * 1000.0, 1)
                result = results[0]

                crossing_this_frame = False
                boxes = result.boxes
                if boxes is not None and boxes.id is not None:
                    xyxy = boxes.xyxy.cpu().tolist()
                    ids = boxes.id.int().cpu().tolist()
                    classes = boxes.cls.int().cpu().tolist()
                    confs = boxes.conf.cpu().tolist()
                    claimed_canonical_ids: set[int] = set()
                    for rect_roi, track_id_raw, cls_id, confidence in zip(xyxy, ids, classes, confs):
                        raw_track_id = int(track_id_raw)
                        rx1, ry1, rx2, ry2 = rect_roi
                        rect = (rx1 + offset_x, ry1 + offset_y, rx2 + offset_x, ry2 + offset_y)
                        x1, y1, x2, y2 = rect
                        center = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
                        current_label = str(result.names[int(cls_id)])
                        confidence_f = float(confidence)

                        track_id, stitched = self._continuity.resolve(
                            raw_track_id,
                            center,
                            current_label,
                            frame_index,
                            width,
                            height,
                            claimed_canonical_ids,
                        )
                        claimed_canonical_ids.add(track_id)
                        if stitched:
                            self.state.stitch_recoveries = self._continuity.stitch_count

                        velocity = self._continuity.velocity_for(track_id)
                        anchor = motion_leading_anchor(rect, velocity)
                        self._seen_track_ids.add(track_id)
                        self._labels.update(track_id, current_label, confidence_f)
                        stable_label, class_certainty, class_hits = self._labels.stable_label(track_id, current_label)

                        direction = counter.update(track_id, anchor, width, height, frame_index=frame_index)
                        display_label = stable_label if class_hits >= 2 else current_label
                        self._draw_detection(
                            cv2,
                            frame,
                            rect,
                            track_id,
                            display_label,
                            confidence_f,
                            anchor,
                            class_certainty,
                            raw_track_id,
                        )

                        if direction:
                            crossing_this_frame = True
                            refined = None
                            needs_refine = self.refine_at_crossing and (
                                display_label in AMBIGUOUS_CLASSES
                                and (display_label in {"bicycle", "motorcycle", "bus", "truck"} or class_certainty < 0.82 or class_hits < 4)
                            )
                            if needs_refine:
                                refined = self._refine_crossing_label(frame, rect, device, use_half, refine_ids)

                            event_label, policy_conf = self._class_policy.final_label(
                                current_label,
                                stable_label,
                                class_certainty,
                                class_hits,
                                refined,
                            )
                            event_label = event_label if event_label in VEHICLE_CLASSES else "other"
                            refined_conf = refined[1] if refined is not None else 0.0
                            event_confidence = max(confidence_f, policy_conf, refined_conf)

                            self.state.total_count += 1
                            self.state.counts_by_type[event_label] = self.state.counts_by_type.get(event_label, 0) + 1
                            self.state.in_count = counter.in_count
                            self.state.out_count = counter.out_count
                            self.state.rescued_crossings = counter.rescued_crossings
                            snapshot = self._save_snapshot(cv2, frame, track_id)
                            self._event_dispatcher.submit(
                                self._event_payload(track_id, event_label, direction, event_confidence, snapshot)
                            )

                self.state.detected_tracks = len(self._seen_track_ids)
                self._draw_overlay(cv2, frame, counter)
                self.state.processed_frames += 1
                if crossing_this_frame or self.state.processed_frames % self.jpeg_every_n == 0:
                    self._jpeg_encoder.submit(frame)

                elapsed = max(time.perf_counter() - (loop_started or time.perf_counter()), 0.001)

                # Local MP4 playback is displayed natively by the browser in V0.4.1.
                # When AI is faster than the source, pace it to the source clock so
                # counters/annotations do not race far ahead of the smooth video.
                # When AI is slower we never drop source frames; lag is reported.
                if self.payload.source_type == "video" and self.video_pace and self.state.source_fps > 0:
                    target_elapsed = self.state.processed_frames / self.state.source_fps
                    ahead = target_elapsed - elapsed
                    if ahead > 0:
                        time.sleep(min(ahead, 0.05))
                        elapsed = max(time.perf_counter() - (loop_started or time.perf_counter()), 0.001)
                    self.state.playback_lag_seconds = round(max(0.0, elapsed - target_elapsed), 3)

                self.state.fps = round(self.state.processed_frames / elapsed, 2)
                if self.state.source_fps > 0:
                    self.state.realtime_factor = round(self.state.fps / self.state.source_fps, 3)
                if self.state.source_frame_count > 0:
                    self.state.processing_progress = round(min(100.0, self.state.processed_frames * 100.0 / self.state.source_frame_count), 1)

            if self.state.status == "running":
                self.state.status = "stopped"
        except Exception as exc:
            self.state.status = "error"
            self.state.last_error = str(exc)
        finally:
            if cap is not None:
                cap.release()
            try:
                if self._jpeg_encoder.is_alive():
                    self._jpeg_encoder.stop_and_join(timeout=4.0)
            except Exception:
                pass
            try:
                if self._event_dispatcher.is_alive():
                    self._event_dispatcher.stop_and_flush(timeout=20.0)
            except Exception as exc:
                self.state.last_error = self.state.last_error or f"Event dispatcher shutdown failed: {exc}"
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
        return cv2.resize(frame, (self.process_max_width, max(2, int(round(height * scale)))), interpolation=cv2.INTER_AREA)

    @staticmethod
    def _vehicle_class_ids(names) -> list[int]:
        mapping = names.items() if isinstance(names, dict) else enumerate(names)
        return [int(idx) for idx, name in mapping if str(name) in VEHICLE_CLASSES]

    @staticmethod
    def _named_class_ids(names, labels: set[str]) -> list[int]:
        mapping = names.items() if isinstance(names, dict) else enumerate(names)
        return [int(idx) for idx, name in mapping if str(name) in labels]

    def _refine_crossing_label(self, frame, rect, device, use_half: bool, refine_ids: list[int]) -> tuple[str, float] | None:
        if self._refiner_model is None or not refine_ids:
            return None
        try:
            h, w = frame.shape[:2]
            x1, y1, x2, y2 = rect
            pad_x = max(12, int((x2 - x1) * 0.24))
            pad_y = max(12, int((y2 - y1) * 0.24))
            ix1 = max(0, int(x1) - pad_x)
            iy1 = max(0, int(y1) - pad_y)
            ix2 = min(w, int(x2) + pad_x)
            iy2 = min(h, int(y2) + pad_y)
            crop = frame[iy1:iy2, ix1:ix2]
            if crop.size == 0 or crop.shape[0] < 32 or crop.shape[1] < 32:
                return None
            predictions = self._refiner_model.predict(
                crop,
                conf=0.08,
                classes=refine_ids,
                device=device,
                imgsz=self.refine_imgsz,
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
            if label not in VEHICLE_CLASSES:
                return None
            return label, float(confs[best_index])
        except Exception:
            return None

    @staticmethod
    def _draw_detection(cv2, frame, rect, track_id: int, label: str, confidence: float, anchor, class_certainty: float, raw_track_id: int | None = None) -> None:
        x1, y1, x2, y2 = [int(v) for v in rect]
        cv2.rectangle(frame, (x1, y1), (x2, y2), (60, 220, 120), 2)
        cv2.circle(frame, (int(anchor[0]), int(anchor[1])), 5, (255, 220, 0), -1)
        text = f"{label} #{track_id} {confidence:.2f}"
        if raw_track_id is not None and raw_track_id != track_id:
            text += f" r{raw_track_id}"
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
        rt = f"x{self.state.realtime_factor:.2f}" if self.state.source_fps > 0 else "live"
        cv2.putText(
            frame,
            f"TOTAL {self.state.total_count} | IN {counter.in_count} | OUT {counter.out_count} | FPS {self.state.fps:.1f} ({rt}) | {self.state.inference_ms:.0f}ms | RESCUE {counter.rescued_crossings}",
            (20, 32),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (0, 200, 255),
            2,
        )
        if self.state.pending_events:
            cv2.putText(frame, f"DB QUEUE {self.state.pending_events}", (20, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 165, 255), 2)

    def _save_snapshot(self, cv2, frame, track_id: int) -> str | None:
        try:
            folder = self.snapshot_root / f"camera_{self.payload.camera_id}"
            folder.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            path = folder / f"{stamp}_track_{track_id}.jpg"
            cv2.imwrite(str(path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
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
