from __future__ import annotations

import os
import json
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import httpx2 as httpx

from app.async_tasks import EventDispatcher, LatestFrameEncoder
from app.benchmark_trace import trace_path
from app.classification import (
    RefineCandidate,
    RefineEvidenceAccumulator,
    TrackLabelSmoother,
    TruckSemanticLock,
    VehicleClassPolicy,
    select_target_refinement,
    vehicle_family,
)
from app.counting import CountingLine, HeavyVehicleCrossingRescuer, LineCrossingCounter, RoadZone, signed_distance
from app.dedup import single_heavy_vehicle_plan
from app.flow_calibration import FlowCalibrator
from app.gate_roi import gate_roi_for_line, road_zone_roi
from app.human_guard import (
    TWO_WHEEL_LABELS,
    HumanGuardTrackPolicy,
    box_iou,
    coverage_of_target,
    human_dominates_two_wheel_candidate,
    is_person_like_two_wheel_box,
    nearby_two_wheel_support,
)
from app.schemas import PipelineStart
from app.tracking import TrackContinuityResolver, motion_leading_anchor

VEHICLE_CLASSES = {"bicycle", "car", "motorcycle", "bus", "truck"}
REFINE_VEHICLE_CLASSES = {"bicycle", "car", "motorcycle", "bus", "truck"}
AMBIGUOUS_CLASSES = {"bicycle", "motorcycle", "car", "bus", "truck"}


def startup_grace_frames_for_source(source_type: str) -> int:
    if str(source_type).strip().lower() == "video":
        return max(0, int(os.getenv("AI_VIDEO_STARTUP_GRACE_FRAMES", "0")))
    return max(0, int(os.getenv("AI_GATE_STARTUP_GRACE_FRAMES", "12")))


@dataclass(slots=True)
class _PendingGuardCrossing:
    track_id: int
    label: str
    direction: str
    confidence: float
    frame_index: int
    source_time_seconds: float | None
    crossing_method: str | None
    crossing_x: float | None
    crossing_y: float | None
    snapshot_frame: object


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
            bicycle_certainty=float(os.getenv("AI_BICYCLE_CERTAINTY", "0.80")),
            bicycle_hits=int(os.getenv("AI_BICYCLE_MIN_HITS", "5")),
            strong_bicycle_certainty=float(os.getenv("AI_BICYCLE_STRONG_CERTAINTY", "0.90")),
            strong_bicycle_hits=int(os.getenv("AI_BICYCLE_STRONG_HITS", "8")),
            bicycle_refine_override_conf=float(os.getenv("AI_BICYCLE_REFINE_OVERRIDE_CONF", "0.58")),
            truck_refine_override_conf=float(os.getenv("AI_TRUCK_REFINE_OVERRIDE_CONF", "0.48")),
            heavy_refine_override_conf=float(os.getenv("AI_HEAVY_REFINE_OVERRIDE_CONF", "0.54")),
        )
        self._refiner_model = None
        self._general_refiner_model = None
        self._class_refine_last_check: dict[int, int] = {}
        self._class_refine_last_observation: dict[int, tuple[int, tuple[str, float] | None]] = {}
        self._class_refine_overrides: dict[int, tuple[str, float, int]] = {}
        self._bicycle_class_rescue_tracks: set[int] = set()
        self._truck_class_rescue_tracks: set[int] = set()
        self._class_consensus_rescue_tracks: set[int] = set()
        self._truck_tracks_seen: set[int] = set()
        self._truck_crossing_tracks: set[int] = set()
        self._four_wheel_duplicate_pairs: set[tuple[int, int]] = set()
        self._bicycle_tracks_seen: set[int] = set()
        self._video_start_rescue_tracks: set[int] = set()
        self._heavy_anchor_tracks: set[int] = set()
        self._heavy_center_rescue_tracks: set[int] = set()
        self._refine_ids: list[int] = []
        self._general_refine_ids: list[int] = []
        self._refiner_thread: threading.Thread | None = None
        self._human_guard_model = None
        self._human_guard_ids: list[int] = []
        self._human_guard_thread: threading.Thread | None = None
        self._human_guard_last_check: dict[int, int] = {}
        self._human_guard_last_observation: dict[int, tuple[int, str, object | None]] = {}
        self._human_guard_policy = HumanGuardTrackPolicy(required_strikes=max(1, int(os.getenv("AI_HUMAN_GUARD_REQUIRED_STRIKES", "2"))))
        self._human_rider_tracks_seen: set[int] = set()
        self._pending_guard_crossings: dict[int, _PendingGuardCrossing] = {}
        self._committed_in_count = 0
        self._committed_out_count = 0
        self._flow_calibrator = FlowCalibrator(
            history_frames=int(os.getenv("AI_FLOW_CALIBRATION_HISTORY_FRAMES", "1200")),
            per_track_points=int(os.getenv("AI_FLOW_CALIBRATION_POINTS_PER_TRACK", "180")),
        )
        self._continuity = TrackContinuityResolver(
            max_gap_frames=int(os.getenv("AI_STITCH_MAX_GAP", "30")),
            max_distance_ratio=float(os.getenv("AI_STITCH_DISTANCE_RATIO", "0.14")),
            heavy_max_gap_frames=int(os.getenv("AI_STITCH_HEAVY_MAX_GAP", "90")),
            heavy_max_distance_ratio=float(os.getenv("AI_STITCH_HEAVY_DISTANCE_RATIO", "0.18")),
        )
        self.backend_url = os.getenv("BACKEND_INTERNAL_URL", "http://backend:8000/api/internal")
        self.shared_token = os.getenv("AI_SHARED_TOKEN", "TrafficAI-Local-2026")
        self.model_name = payload.model_path or os.getenv("AI_MODEL_NAME", "yolo26s.pt")
        self.hybrid_recall = os.getenv("AI_HYBRID_RECALL", "1").strip().lower() not in {"0", "false", "no"}
        self.recall_model_name = os.getenv("AI_RECALL_MODEL_NAME", "yolo26s.pt")
        self.detector_model_name = self.model_name
        self.hybrid_mode = False
        self.device = os.getenv("AI_DEVICE", "auto")
        self.snapshot_root = Path(os.getenv("SNAPSHOT_DIR", "/tmp/traffic-ai-snapshots"))
        self.imgsz = int(os.getenv("AI_IMGSZ", "960"))
        self.process_max_width = int(os.getenv("AI_PROCESS_MAX_WIDTH", "1440"))
        self.jpeg_quality = int(os.getenv("AI_JPEG_QUALITY", "70"))
        self.jpeg_every_n = max(1, int(os.getenv("AI_STREAM_EVERY_N", "2")))
        self.jpeg_max_width = int(os.getenv("AI_STREAM_MAX_WIDTH", "960"))
        self.gate_roi_enabled = os.getenv("AI_GATE_ROI", "1").strip().lower() not in {"0", "false", "no"}
        self.detection_roi_mode = os.getenv("AI_DETECTION_ROI", "full").strip().lower()
        self.road_roi_margin = float(os.getenv("AI_ROAD_ROI_MARGIN", "0.02"))
        self.gate_roi_margin = float(os.getenv("AI_GATE_ROI_MARGIN", "0.16"))
        self.gate_roi_min_span = float(os.getenv("AI_GATE_ROI_MIN_SPAN", "0.52"))
        self.gate_endpoint_margin = float(os.getenv("AI_GATE_ENDPOINT_MARGIN", "0.035"))
        self.refine_at_crossing = os.getenv("AI_REFINE_AT_CROSSING", "1").strip().lower() not in {"0", "false", "no"}
        self.refine_model_name = os.getenv("AI_REFINE_MODEL_NAME", "yolo26m.pt")
        self.general_refine_model_name = os.getenv("AI_GENERAL_REFINE_MODEL_NAME", self.refine_model_name)
        self.dual_class_refine = os.getenv("AI_DUAL_CLASS_REFINE", "1").strip().lower() not in {"0", "false", "no"}
        self.refine_imgsz = int(os.getenv("AI_REFINE_IMGSZ", "640"))
        self.refine_max_per_frame = max(0, int(os.getenv("AI_REFINE_MAX_PER_FRAME", "2")))
        self.refine_max_lag = max(0.0, float(os.getenv("AI_REFINE_MAX_LAG", "0.35")))
        self.refine_background_warmup = os.getenv("AI_REFINE_BACKGROUND_WARMUP", "1").strip().lower() not in {"0", "false", "no"}
        self.class_refine_interval = max(1, int(os.getenv("AI_CLASS_REFINE_INTERVAL", "10")))
        self.class_refine_heavy_interval = max(1, int(os.getenv("AI_CLASS_REFINE_HEAVY_INTERVAL", "45")))
        self.class_refine_gate_distance_ratio = max(0.01, float(os.getenv("AI_CLASS_REFINE_GATE_DISTANCE_RATIO", "0.11")))
        self.class_override_ttl_frames = max(8, int(os.getenv("AI_CLASS_OVERRIDE_TTL_FRAMES", "180")))
        self.bicycle_override_ttl_frames = max(8, int(os.getenv("AI_BICYCLE_OVERRIDE_TTL_FRAMES", "60")))
        self.heavy_override_ttl_frames = max(8, int(os.getenv("AI_HEAVY_OVERRIDE_TTL_FRAMES", "240")))
        self.refine_target_min_iou = max(0.0, float(os.getenv("AI_REFINE_TARGET_MIN_IOU", "0.08")))
        self.refine_target_min_coverage = max(0.0, float(os.getenv("AI_REFINE_TARGET_MIN_COVERAGE", "0.16")))
        self.refine_consensus_min_hits = max(2, int(os.getenv("AI_REFINE_CONSENSUS_MIN_HITS", "2")))
        self.refine_consensus_history_frames = max(20, int(os.getenv("AI_REFINE_CONSENSUS_HISTORY_FRAMES", "120")))
        self.bicycle_consensus_conf = float(os.getenv("AI_BICYCLE_CONSENSUS_CONF", "0.60"))
        self.bicycle_consensus_min_hits = max(2, int(os.getenv("AI_BICYCLE_CONSENSUS_MIN_HITS", "3")))
        self.bicycle_consensus_margin = max(0.0, float(os.getenv("AI_BICYCLE_CONSENSUS_MARGIN", "0.08")))
        self.bicycle_consensus_min_strong = max(0.0, float(os.getenv("AI_BICYCLE_CONSENSUS_MIN_STRONG", "0.34")))
        self.truck_consensus_conf = float(os.getenv("AI_TRUCK_CONSENSUS_CONF", "0.52"))
        self._refine_consensus = RefineEvidenceAccumulator(history_frames=self.refine_consensus_history_frames)
        self._truck_semantic_lock = TruckSemanticLock(
            ttl_frames=int(os.getenv("AI_TRUCK_SEMANTIC_LOCK_FRAMES", "450")),
            min_refiner_hits=int(os.getenv("AI_TRUCK_SEMANTIC_LOCK_MIN_HITS", "2")),
            min_refiner_confidence=float(os.getenv("AI_TRUCK_SEMANTIC_LOCK_CONF", "0.62")),
            primary_hits=int(os.getenv("AI_TRUCK_SEMANTIC_PRIMARY_HITS", "3")),
            primary_certainty=float(os.getenv("AI_TRUCK_SEMANTIC_PRIMARY_CERTAINTY", "0.80")),
        )
        self.human_guard_enabled = os.getenv("AI_HUMAN_GUARD", "1").strip().lower() not in {"0", "false", "no"}
        self.human_guard_model_name = os.getenv("AI_HUMAN_GUARD_MODEL", self.recall_model_name)
        self.human_guard_imgsz = int(os.getenv("AI_HUMAN_GUARD_IMGSZ", "512"))
        self.human_guard_check_interval = max(1, int(os.getenv("AI_HUMAN_GUARD_CHECK_INTERVAL", "8")))
        self.human_guard_conf = float(os.getenv("AI_HUMAN_GUARD_CONF", "0.08"))
        self.human_guard_pending_max_frames = max(2, int(os.getenv("AI_HUMAN_GUARD_PENDING_MAX_FRAMES", "12")))
        self.warmup = os.getenv("AI_WARMUP", "1").strip().lower() not in {"0", "false", "no"}
        self.video_pace = os.getenv("AI_VIDEO_PACE", "1").strip().lower() not in {"0", "false", "no"}
        self.iou = float(os.getenv("AI_IOU", "0.55"))
        self.agnostic_nms = os.getenv("AI_AGNOSTIC_NMS", "0").strip().lower() not in {"0", "false", "no"}
        self.heavy_duplicate_iou = float(os.getenv("AI_HEAVY_DUP_IOU", "0.68"))
        self.heavy_anchor_inset_ratio = max(0.0, min(0.40, float(os.getenv("AI_HEAVY_ANCHOR_INSET_RATIO", "0.16"))))
        self.heavy_center_rescue_enabled = os.getenv("AI_HEAVY_CENTER_RESCUE", "1").strip().lower() not in {"0", "false", "no"}
        self.heavy_center_history_gap = max(8, int(os.getenv("AI_HEAVY_CENTER_HISTORY_GAP", "90")))
        self.heavy_center_min_normal_ratio = max(0.0, min(1.0, float(os.getenv("AI_HEAVY_CENTER_MIN_NORMAL_RATIO", "0.20"))))
        self.heavy_center_road_margin_ratio = max(0.0, float(os.getenv("AI_HEAVY_CENTER_ROAD_MARGIN_RATIO", "0.020")))
        self.video_origin_rescue_frames = max(0, int(os.getenv("AI_VIDEO_ORIGIN_RESCUE_FRAMES", "20")))
        self.video_origin_distance_ratio = max(0.0, float(os.getenv("AI_VIDEO_ORIGIN_DISTANCE_RATIO", "0.065")))
        self.video_origin_min_normal_ratio = max(0.0, min(1.0, float(os.getenv("AI_VIDEO_ORIGIN_MIN_NORMAL_RATIO", "0.30"))))
        self.tracker_config = str(Path(__file__).with_name("bytetrack_traffic.yaml"))
        self._event_dispatcher = EventDispatcher(self.backend_url, self.shared_token, self.state)
        self._jpeg_encoder = LatestFrameEncoder(self._set_latest_jpeg, self.state, self.jpeg_quality, self.jpeg_max_width)
        self.benchmark_trace_enabled = os.getenv("AI_BENCHMARK_TRACE", "1").strip().lower() not in {"0", "false", "no"}

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

    def calibration_proposal(self) -> dict:
        result = self._flow_calibrator.proposal()
        result["camera_id"] = self.payload.camera_id
        result["session_id"] = self.payload.session_id
        return result

    def _start_refiner_background(self, YOLO, np, device, use_half: bool) -> None:
        if not self.refine_at_crossing or self._refiner_thread is not None:
            return

        def warm_model(model, ids: list[int]) -> None:
            if self.warmup and ids and not self._stop_event.is_set():
                dummy = np.zeros(
                    (min(self.refine_imgsz, self.imgsz), min(self.refine_imgsz, self.imgsz), 3),
                    dtype=np.uint8,
                )
                model.predict(
                    dummy,
                    conf=0.10,
                    classes=ids,
                    device=device,
                    imgsz=min(self.refine_imgsz, self.imgsz),
                    half=use_half,
                    verbose=False,
                )

        def load_refiner() -> None:
            # Primary/domain refiner. In Hybrid Recall this is the activated
            # best.pt; otherwise it is the configured AI_REFINE_MODEL_NAME.
            try:
                model = YOLO(self.refine_model_name)
                ids = self._named_class_ids(model.names, REFINE_VEHICLE_CLASSES)
                warm_model(model, ids)
                if not self._stop_event.is_set():
                    self._refiner_model = model
                    self._refine_ids = ids
                    self.state.refine_model_name = self.refine_model_name if ids else None
            except Exception:
                # Refiners are optional. Detector/tracker/counting must keep
                # running even if a secondary model cannot load.
                self._refiner_model = None
                self._refine_ids = []

            # V0.5.27 Dual Refiner Consensus: when best.pt is activated, keep a
            # general pretrained YOLO26m verifier as an independent second
            # opinion. This is especially useful for rare bicycle/truck classes
            # that may be under-represented in the custom training set.
            self._general_refiner_model = None
            self._general_refine_ids = []
            self.state.general_refine_model_name = None
            if (
                self.dual_class_refine
                and str(self.general_refine_model_name)
                and Path(str(self.general_refine_model_name)).name != Path(str(self.refine_model_name)).name
                and not self._stop_event.is_set()
            ):
                try:
                    general = YOLO(self.general_refine_model_name)
                    general_ids = self._named_class_ids(general.names, REFINE_VEHICLE_CLASSES)
                    warm_model(general, general_ids)
                    if not self._stop_event.is_set() and general_ids:
                        self._general_refiner_model = general
                        self._general_refine_ids = general_ids
                        self.state.general_refine_model_name = self.general_refine_model_name
                except Exception:
                    self._general_refiner_model = None
                    self._general_refine_ids = []

        self._refiner_thread = threading.Thread(
            target=load_refiner, daemon=True, name=f"refiner-{self.payload.camera_id}"
        )
        self._refiner_thread.start()

    def _start_human_guard_background(self, YOLO, np, device, use_half: bool) -> None:
        if not self.human_guard_enabled or self._human_guard_thread is not None:
            return

        def load_guard() -> None:
            try:
                model = YOLO(self.human_guard_model_name)
                ids = self._named_class_ids(model.names, {"person", "motorcycle", "bicycle"})
                if self.warmup and ids and not self._stop_event.is_set():
                    dummy = np.zeros((min(self.human_guard_imgsz, self.imgsz), min(self.human_guard_imgsz, self.imgsz), 3), dtype=np.uint8)
                    model.predict(dummy, conf=self.human_guard_conf, classes=ids, device=device, imgsz=min(self.human_guard_imgsz, self.imgsz), half=use_half, verbose=False)
                if not self._stop_event.is_set():
                    self._human_guard_model = model
                    self._human_guard_ids = ids
                    self.state.human_guard_ready = bool(ids)
            except Exception:
                self._human_guard_model = None
                self._human_guard_ids = []
                self.state.human_guard_ready = False

        self._human_guard_thread = threading.Thread(target=load_guard, daemon=True, name=f"human-guard-{self.payload.camera_id}")
        self._human_guard_thread.start()

    def _verify_human_candidate(self, frame, rect, target_label: str, target_confidence: float, device, use_half: bool, velocity=(0.0, 0.0)):
        if self._human_guard_model is None or not self._human_guard_ids or target_label not in TWO_WHEEL_LABELS:
            return None
        try:
            from math import hypot

            h, w = frame.shape[:2]
            x1, y1, x2, y2 = [float(v) for v in rect]
            target_w = max(1.0, x2 - x1)
            target_h = max(1.0, y2 - y1)
            # V0.5.24: expand much farther below the PERSON-like candidate. In
            # the supplied camera snapshots the rider torso receives the tall
            # MOTORCYCLE box while the physical scooter sits below it.
            pad_left = max(20, int(target_w * 0.72))
            pad_right = max(20, int(target_w * 0.72))
            pad_top = max(16, int(target_h * 0.22))
            pad_bottom = max(28, int(target_h * 1.05))
            ix1, iy1 = max(0, int(x1) - pad_left), max(0, int(y1) - pad_top)
            ix2, iy2 = min(w, int(x2) + pad_right), min(h, int(y2) + pad_bottom)
            crop = frame[iy1:iy2, ix1:ix2]
            if crop.size == 0 or crop.shape[0] < 40 or crop.shape[1] < 28:
                return None
            predictions = self._human_guard_model.predict(
                crop, conf=self.human_guard_conf, classes=self._human_guard_ids, device=device,
                imgsz=self.human_guard_imgsz, half=use_half, verbose=False,
            )
            if not predictions or predictions[0].boxes is None:
                return None
            target_crop = (x1 - ix1, y1 - iy1, x2 - ix1, y2 - iy1)
            best_person = None
            best_person_conf = 0.0
            best_vehicle_conf = 0.0
            best_nearby_vehicle_conf = 0.0
            boxes = predictions[0].boxes
            crop_h, crop_w = crop.shape[:2]
            for box, cls_id, conf in zip(boxes.xyxy.cpu().tolist(), boxes.cls.int().cpu().tolist(), boxes.conf.cpu().tolist()):
                label = str(predictions[0].names[int(cls_id)])
                evidence = tuple(map(float, box))
                overlap = max(box_iou(target_crop, evidence), coverage_of_target(target_crop, evidence))
                if label == "person":
                    if overlap >= 0.18 and float(conf) > best_person_conf:
                        best_person = evidence
                        best_person_conf = float(conf)
                    continue
                if label in TWO_WHEEL_LABELS:
                    if overlap >= 0.18:
                        best_vehicle_conf = max(best_vehicle_conf, float(conf))
                    elif nearby_two_wheel_support(target_crop, evidence, crop_w, crop_h):
                        best_nearby_vehicle_conf = max(best_nearby_vehicle_conf, float(conf))
            self.state.human_guard_checks += 1
            diagonal = max(hypot(w, h), 1.0)
            speed_ratio = hypot(float(velocity[0]), float(velocity[1])) / diagonal
            return human_dominates_two_wheel_candidate(
                target_crop, target_label, float(target_confidence), best_person, best_person_conf,
                best_vehicle_conf, best_nearby_vehicle_conf, speed_ratio,
            )
        except Exception:
            return None

    def _observe_human_guard(
        self,
        track_id: int,
        frame_index: int,
        frame,
        rect,
        label: str,
        confidence: float,
        device,
        use_half: bool,
        *,
        velocity=(0.0, 0.0),
        force: bool = False,
    ):
        """Run Human Guard at most once for one track/source-frame.

        V0.5.24 could inspect the same pixels in the periodic branch and again
        at crossing time. V0.5.25 caches that observation so one source frame
        can contribute at most one strike. A forced crossing/follow-up check
        bypasses the interval, but never the same-frame cache.
        """
        tid = int(track_id)
        frame_idx = int(frame_index)
        cached = self._human_guard_last_observation.get(tid)
        if cached is not None and cached[0] == frame_idx:
            return cached[1], cached[2]

        last_guard = self._human_guard_last_check.get(tid, -10_000)
        if not force and frame_idx - last_guard < self.human_guard_check_interval:
            return self._human_guard_policy.status(tid), None

        self._human_guard_last_check[tid] = frame_idx
        was_rejected = self._human_guard_policy.is_rejected(tid)
        decision = self._verify_human_candidate(
            frame, rect, label, confidence, device, use_half, velocity=velocity
        )
        action = self._human_guard_policy.observe(tid, decision, frame_index=frame_idx)
        self._human_guard_last_observation[tid] = (frame_idx, action, decision)

        if action in {"rider", "released"} and tid not in self._human_rider_tracks_seen:
            self.state.rider_guard_rescues += 1
            self._human_rider_tracks_seen.add(tid)
        if action == "rejected" and not was_rejected:
            self.state.human_guard_rejections += 1
        return action, decision

    def _record_committed_crossing(self, label: str, direction: str, crossing_method: str | None) -> None:
        self.state.total_count += 1
        self.state.counts_by_type[label] = self.state.counts_by_type.get(label, 0) + 1
        if direction == "in":
            self._committed_in_count += 1
        elif direction == "out":
            self._committed_out_count += 1
        self.state.in_count = self._committed_in_count
        self.state.out_count = self._committed_out_count
        if crossing_method == "direct":
            self.state.direct_crossings += 1
        elif crossing_method == "interpolated":
            self.state.interpolated_crossings += 1
        elif crossing_method == "rescued":
            self.state.rescued_crossings += 1

    def _commit_guard_crossing(self, cv2, pending: _PendingGuardCrossing) -> None:
        snapshot = self._save_crossing_snapshot(cv2, pending.snapshot_frame, pending.frame_index)
        self._record_committed_crossing(pending.label, pending.direction, pending.crossing_method)
        self._event_dispatcher.submit(
            self._event_payload(
                pending.track_id, pending.label, pending.direction, pending.confidence, snapshot,
                pending.frame_index, pending.source_time_seconds, pending.crossing_method,
                pending.crossing_x, pending.crossing_y,
            )
        )
        self.state.human_guard_deferred_commits += 1
        self._pending_guard_crossings.pop(int(pending.track_id), None)
        self.state.human_guard_pending_crossings = len(self._pending_guard_crossings)

    def _drop_guard_crossing(self, counter: LineCrossingCounter, pending: _PendingGuardCrossing, *, expired: bool = False) -> None:
        counter.revoke_last_crossing(pending.track_id, pending.direction)
        self._pending_guard_crossings.pop(int(pending.track_id), None)
        self.state.human_guard_pending_crossings = len(self._pending_guard_crossings)
        if expired:
            self.state.human_guard_pending_drops += 1

    def _refresh_truck_semantic_lock(
        self,
        track_id: int,
        frame_index: int,
        stable_label: str,
        certainty: float,
        hits: int,
    ) -> tuple[str, float] | None:
        truck_hits, truck_fused, _strongest = self._refine_consensus.support(
            track_id, frame_index, "truck"
        )
        locked = self._truck_semantic_lock.observe(
            track_id,
            frame_index,
            stable_label=stable_label,
            certainty=certainty,
            hits=hits,
            refiner_hits=truck_hits,
            refiner_confidence=truck_fused,
        )
        if locked is not None:
            self._truck_tracks_seen.add(int(track_id))
            self.state.truck_tracks_seen = len(self._truck_tracks_seen)
            self.state.truck_semantic_locks = len(self._truck_tracks_seen)
        return locked

    @staticmethod
    def _move_track_key(mapping: dict, source_track_id: int, target_track_id: int) -> None:
        source = int(source_track_id)
        target = int(target_track_id)
        if source == target or source not in mapping:
            return
        source_value = mapping.pop(source)
        if target not in mapping:
            mapping[target] = source_value
            return
        target_value = mapping[target]
        if isinstance(source_value, int) and isinstance(target_value, int):
            mapping[target] = max(source_value, target_value)
            return
        if isinstance(source_value, tuple) and isinstance(target_value, tuple):
            # last-check tuples are (frame, value); overrides are
            # (label, confidence, frame). Pick the newest source frame.
            if len(source_value) == 2 and len(target_value) == 2 and isinstance(source_value[0], int) and isinstance(target_value[0], int):
                mapping[target] = source_value if source_value[0] >= target_value[0] else target_value
                return
            if len(source_value) >= 3 and len(target_value) >= 3 and isinstance(source_value[-1], int) and isinstance(target_value[-1], int):
                mapping[target] = source_value if source_value[-1] >= target_value[-1] else target_value

    def _merge_canonical_track_state(
        self,
        source_track_id: int,
        target_track_id: int,
        counter: LineCrossingCounter,
        heavy_rescuer: HeavyVehicleCrossingRescuer | None,
    ) -> None:
        """Merge semantic/gate state after one CAR/TRUCK/BUS ID is aliased."""
        source = int(source_track_id)
        target = int(target_track_id)
        if source == target:
            return
        counter.merge_track(source, target)
        if heavy_rescuer is not None:
            heavy_rescuer.merge_track(source, target)
        self._labels.merge_track(source, target)
        self._refine_consensus.merge_track(source, target)
        self._truck_semantic_lock.rebind(source, target)
        for mapping in (
            self._class_refine_last_check,
            self._class_refine_last_observation,
            self._class_refine_overrides,
        ):
            self._move_track_key(mapping, source, target)
        for bucket in (
            self._seen_track_ids,
            self._truck_tracks_seen,
            self._truck_crossing_tracks,
            self._bicycle_tracks_seen,
            self._bicycle_class_rescue_tracks,
            self._truck_class_rescue_tracks,
            self._class_consensus_rescue_tracks,
            self._heavy_anchor_tracks,
            self._heavy_center_rescue_tracks,
        ):
            if source in bucket:
                bucket.discard(source)
                bucket.add(target)
        self.state.truck_tracks_seen = len(self._truck_tracks_seen)
        self.state.truck_crossing_tracks = len(self._truck_crossing_tracks)
        self.state.truck_semantic_locks = len(self._truck_tracks_seen)
        self.state.heavy_anchor_tracks = len(self._heavy_anchor_tracks)
        self.state.heavy_center_rescues = len(self._heavy_center_rescue_tracks)

    def _class_override_for(self, track_id: int, frame_index: int, primary_label: str) -> tuple[str, float] | None:
        semantic_lock = self._truck_semantic_lock.resolve(track_id, frame_index, primary_label)
        if semantic_lock is not None:
            return semantic_lock
        entry = self._class_refine_overrides.get(int(track_id))
        if entry is None:
            return None
        label, confidence, observed_frame = entry
        ttl = self.class_override_ttl_frames
        if str(label) == "bicycle":
            ttl = self.bicycle_override_ttl_frames
        elif vehicle_family(label) == "four-wheel":
            ttl = self.heavy_override_ttl_frames
        if int(frame_index) - int(observed_frame) > ttl:
            self._class_refine_overrides.pop(int(track_id), None)
            return None
        if vehicle_family(label) != vehicle_family(primary_label):
            self._class_refine_overrides.pop(int(track_id), None)
            return None
        return str(label), float(confidence)

    def _remember_class_refinement(
        self,
        track_id: int,
        frame_index: int,
        current_label: str,
        stable_label: str,
        certainty: float,
        hits: int,
        base_display_label: str,
        refined: tuple[str, float] | None,
    ) -> tuple[str, float] | None:
        if refined is None:
            return self._class_override_for(track_id, frame_index, base_display_label)
        resolved_label, resolved_conf = self._class_policy.final_label(
            current_label, stable_label, certainty, hits, refined
        )
        if vehicle_family(resolved_label) != vehicle_family(base_display_label):
            return self._class_override_for(track_id, frame_index, base_display_label)

        # V0.5.30 semantic hysteresis: a repeatedly confirmed TRUCK must not
        # fall back to CAR only because the close-up crossing frame is COCO-car
        # shaped. Refresh the lock from both temporal detector evidence and
        # distinct-frame refiner consensus, then let it win over one-frame
        # demotions for a bounded TTL.
        semantic_lock = self._refresh_truck_semantic_lock(
            track_id, frame_index, stable_label, certainty, hits
        )
        if semantic_lock is not None and resolved_label in {"car", "bus", "truck"}:
            resolved_label, resolved_conf = semantic_lock

        self._class_refine_overrides[int(track_id)] = (
            str(resolved_label), float(resolved_conf), int(frame_index)
        )
        if resolved_label == "bicycle" and base_display_label != "bicycle" and int(track_id) not in self._bicycle_class_rescue_tracks:
            self._bicycle_class_rescue_tracks.add(int(track_id))
            self.state.bicycle_class_rescues += 1
        if resolved_label == "truck" and base_display_label != "truck" and int(track_id) not in self._truck_class_rescue_tracks:
            self._truck_class_rescue_tracks.add(int(track_id))
            self.state.truck_class_rescues += 1
        return str(resolved_label), float(resolved_conf)

    def _prefer_refinement_candidate(
        self, target_label: str, candidates: list[tuple[str, float]]
    ) -> tuple[str, float] | None:
        valid = [(str(label), float(conf)) for label, conf in candidates if str(label) in VEHICLE_CLASSES]
        if not valid:
            return None
        target = str(target_label)
        family = vehicle_family(target)

        # Prefer a credible minority-class correction over a very confident
        # repeat of the recall-detector class. This lets YOLO26m disagree with
        # best.pt on a bicycle/truck without the common motorcycle/car class
        # automatically winning only because it has the larger confidence.
        if family == "two-wheel" and target != "bicycle":
            bicycles = [item for item in valid if item[0] == "bicycle"]
            if bicycles:
                candidate = max(bicycles, key=lambda item: item[1])
                if candidate[1] >= self._class_policy.bicycle_refine_override_conf:
                    return candidate
        if family == "four-wheel" and target != "truck":
            trucks = [item for item in valid if item[0] == "truck"]
            if trucks:
                candidate = max(trucks, key=lambda item: item[1])
                if candidate[1] >= self._class_policy.truck_refine_override_conf:
                    return candidate
        if family == "four-wheel" and target != "bus":
            buses = [item for item in valid if item[0] == "bus"]
            if buses:
                candidate = max(buses, key=lambda item: item[1])
                if candidate[1] >= self._class_policy.heavy_refine_override_conf:
                    return candidate
        return max(valid, key=lambda item: item[1])

    def _observe_class_refiner(
        self,
        track_id: int,
        frame_index: int,
        frame,
        rect,
        target_label: str,
        device,
        use_half: bool,
        *,
        force: bool = False,
    ) -> tuple[tuple[str, float] | None, bool]:
        """Run domain + general refiners and fuse evidence across frames.

        V0.5.26 used exactly one target-aware refiner. With an activated custom
        best.pt that means the configured YOLO26m verifier is replaced, which is
        risky for rare classes that may have few custom examples. V0.5.27 keeps
        best.pt as the domain opinion *and* runs an independent general verifier.
        Repeated low-confidence bicycle/truck evidence can then reach consensus
        across distinct source frames instead of requiring one lucky frame.
        """
        tid = int(track_id)
        frame_idx = int(frame_index)
        cached = self._class_refine_last_observation.get(tid)
        if cached is not None and cached[0] == frame_idx:
            return cached[1], False

        last = self._class_refine_last_check.get(tid, -100000)
        interval = self.class_refine_heavy_interval if vehicle_family(target_label) == "four-wheel" else self.class_refine_interval
        if not force and frame_idx - last < interval:
            return None, False
        if self._refiner_model is None and self._general_refiner_model is None:
            return None, False

        self._class_refine_last_check[tid] = frame_idx
        self.state.class_refine_checks += 1
        observations: list[tuple[str, float]] = []
        did_infer = False

        if self._refiner_model is not None and self._refine_ids:
            self.state.domain_refine_checks += 1
            did_infer = True
            domain = self._refine_crossing_label(
                frame, rect, device, use_half, self._refine_ids,
                target_label=target_label, model=self._refiner_model,
            )
            if domain is not None:
                observations.append(domain)
                self._refine_consensus.update(tid, frame_idx, domain[0], domain[1], "domain")

        if self._general_refiner_model is not None and self._general_refine_ids:
            self.state.general_refine_checks += 1
            did_infer = True
            general = self._refine_crossing_label(
                frame, rect, device, use_half, self._general_refine_ids,
                target_label=target_label, model=self._general_refiner_model,
            )
            if general is not None:
                observations.append(general)
                self._refine_consensus.update(tid, frame_idx, general[0], general[1], "general")

        consensus = self._refine_consensus.minority_consensus(
            tid,
            frame_idx,
            target_label,
            min_hits=self.refine_consensus_min_hits,
            bicycle_confidence=self.bicycle_consensus_conf,
            truck_confidence=self.truck_consensus_conf,
            bicycle_min_hits=self.bicycle_consensus_min_hits,
            bicycle_margin=self.bicycle_consensus_margin,
            bicycle_min_strongest=self.bicycle_consensus_min_strong,
        )
        if consensus is not None:
            if consensus[0] != str(target_label) and tid not in self._class_consensus_rescue_tracks:
                self._class_consensus_rescue_tracks.add(tid)
                self.state.class_consensus_rescues += 1
            refined = consensus
        else:
            refined = self._prefer_refinement_candidate(target_label, observations)

        self._class_refine_last_observation[tid] = (frame_idx, refined)
        return refined, did_infer

    @staticmethod
    def _looks_like_custom_model(model_name: str) -> bool:
        name = Path(str(model_name)).name.lower()
        return name.endswith(".pt") and not name.startswith("yolo26") and not name.startswith("yolo11")

    def run(self) -> None:
        cap = None
        counter = None
        loop_started = None
        trace_file = None
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
            if self.payload.source_type == "video" and self.benchmark_trace_enabled:
                path = trace_path(self.payload.session_id)
                path.parent.mkdir(parents=True, exist_ok=True)
                trace_file = path.open("w", encoding="utf-8", buffering=1)
            self.state.status = "warming"

            # Prime MJPEG immediately with a raw source frame so switching to
            # AI Overlay never shows a black panel while YOLO/CUDA warm up.
            self._jpeg_encoder.start()
            preview_ok, preview_frame = cap.read()
            if preview_ok:
                preview_frame = self._resize_for_processing(cv2, preview_frame)
                cv2.putText(preview_frame, "AI warming up...", (20, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (0, 200, 255), 2)
                self._jpeg_encoder.submit(preview_frame)
                if self.payload.source_type == "video":
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                self.state.overlay_primed = True

            # V0.5.15 hybrid recall mode:
            # - a custom best.pt remains the activated domain model,
            # - but a robust pretrained detector drives full-frame detection + ByteTrack,
            # - the custom best.pt is used as the crossing-time class refiner.
            # This prevents a low-recall fine-tuned detector from making vehicles disappear
            # completely before the tracker/counting stages can see them.
            self.hybrid_mode = self.hybrid_recall and self._looks_like_custom_model(self.model_name)
            self.detector_model_name = self.recall_model_name if self.hybrid_mode else self.model_name
            if self.hybrid_mode:
                self.refine_model_name = self.model_name

            model = YOLO(self.detector_model_name)
            class_ids = self._vehicle_class_ids(model.names)
            if not class_ids:
                raise RuntimeError("YOLO detector does not expose supported vehicle classes")

            if self.warmup:
                dummy = np.zeros((self.imgsz, self.imgsz, 3), dtype=np.uint8)
                model.predict(dummy, conf=0.05, classes=class_ids, device=device, imgsz=self.imgsz, half=use_half, verbose=False)

            road_zone = RoadZone(
                self.payload.road_x1, self.payload.road_y1, self.payload.road_x2, self.payload.road_y2,
                self.payload.road_x3, self.payload.road_y3, self.payload.road_x4, self.payload.road_y4,
            )
            # Local benchmark/video files must not suppress a real crossing that
            # happens in the first few frames (the supplied GT contains a valid
            # crossing at 00:00.160). Live RTSP still keeps startup grace to
            # avoid counting stale tracker initialization around the gate.
            startup_grace_frames = startup_grace_frames_for_source(self.payload.source_type)
            counter = LineCrossingCounter(
                CountingLine(self.payload.line_x1, self.payload.line_y1, self.payload.line_x2, self.payload.line_y2),
                road_zone=road_zone,
                segment_margin=float(os.getenv("AI_GATE_SEGMENT_MARGIN", "0.0")),
                dead_band_ratio=float(os.getenv("AI_GATE_DEAD_BAND_RATIO", "0.006")),
                rearm_distance_ratio=float(os.getenv("AI_GATE_REARM_DISTANCE_RATIO", "0.028")),
                history_gap_frames=int(os.getenv("AI_GATE_HISTORY_GAP", "45")),
                interpolation_gap_frames=int(os.getenv("AI_GATE_INTERPOLATION_GAP", "3")),
                min_perpendicular_ratio=float(os.getenv("AI_GATE_MIN_NORMAL_RATIO", "0.10")),
                min_crossing_motion_ratio=float(os.getenv("AI_GATE_MIN_MOTION_RATIO", "0.004")),
                startup_grace_frames=startup_grace_frames,
                side_confirm_samples=int(os.getenv("AI_GATE_SIDE_CONFIRM_SAMPLES", "2")),
                crossing_cooldown_frames=int(os.getenv("AI_GATE_COOLDOWN_FRAMES", "60")),
                road_anchor_margin_ratio=float(os.getenv("AI_ROAD_ANCHOR_MARGIN_RATIO", "0.012")),
                fast_confirm_distance_ratio=float(os.getenv("AI_GATE_FAST_CONFIRM_DISTANCE_RATIO", "0.018")),
                adaptive_cooldown=os.getenv("AI_GATE_ADAPTIVE_COOLDOWN", "1").strip().lower() not in {"0", "false", "no"},
                cooldown_release_ratio=float(os.getenv("AI_GATE_COOLDOWN_RELEASE_RATIO", "0.055")),
                rescue_min_normal_ratio=float(os.getenv("AI_GATE_RESCUE_MIN_NORMAL_RATIO", "0.28")),
                rescue_max_jump_ratio=float(os.getenv("AI_GATE_RESCUE_MAX_JUMP_RATIO", "0.26")),
                rescue_min_side_distance_ratio=float(os.getenv("AI_GATE_RESCUE_MIN_SIDE_RATIO", "0.010")),
                bracket_confirm=os.getenv("AI_GATE_BRACKET_CONFIRM", "1").strip().lower() not in {"0", "false", "no"},
                bracket_confirm_min_normal_ratio=float(os.getenv("AI_GATE_BRACKET_CONFIRM_MIN_NORMAL_RATIO", "0.55")),
                bracket_confirm_max_gap_frames=int(os.getenv("AI_GATE_BRACKET_CONFIRM_MAX_GAP", "2")),
                origin_rescue_frames=self.video_origin_rescue_frames if self.payload.source_type == "video" else 0,
                origin_rescue_distance_ratio=self.video_origin_distance_ratio,
                origin_rescue_min_normal_ratio=self.video_origin_min_normal_ratio,
            )
            heavy_rescuer = HeavyVehicleCrossingRescuer(
                counter.line,
                road_zone=counter.road_zone,
                history_gap_frames=self.heavy_center_history_gap,
                dead_band_ratio=float(os.getenv("AI_GATE_DEAD_BAND_RATIO", "0.006")),
                segment_margin=float(os.getenv("AI_GATE_SEGMENT_MARGIN", "0.0")),
                min_normal_ratio=self.heavy_center_min_normal_ratio,
                min_motion_ratio=float(os.getenv("AI_GATE_MIN_MOTION_RATIO", "0.004")),
                road_margin_ratio=self.heavy_center_road_margin_ratio,
            ) if self.heavy_center_rescue_enabled else None

            self._event_dispatcher.start()
            self.state.status = "running"
            self.state.model_name = self.model_name
            self.state.detector_model_name = self.detector_model_name
            self.state.hybrid_mode = self.hybrid_mode
            self.state.refine_model_name = None
            self.state.general_refine_model_name = None
            if self.refine_background_warmup:
                self._start_refiner_background(YOLO, np, device, use_half)
            elif self.refine_at_crossing:
                self._refiner_model = YOLO(self.refine_model_name)
                self._refine_ids = self._named_class_ids(self._refiner_model.names, REFINE_VEHICLE_CLASSES)
                self.state.refine_model_name = self.refine_model_name if self._refine_ids else None
                if (
                    self.dual_class_refine
                    and Path(str(self.general_refine_model_name)).name != Path(str(self.refine_model_name)).name
                ):
                    try:
                        self._general_refiner_model = YOLO(self.general_refine_model_name)
                        self._general_refine_ids = self._named_class_ids(
                            self._general_refiner_model.names, REFINE_VEHICLE_CLASSES
                        )
                        if self._general_refine_ids:
                            self.state.general_refine_model_name = self.general_refine_model_name
                    except Exception:
                        self._general_refiner_model = None
                        self._general_refine_ids = []
            self._start_human_guard_background(YOLO, np, device, use_half)
            self.state.imgsz = self.imgsz
            self.state.half_precision = use_half
            self.state.device = "cuda" if device != "cpu" and use_half else "cpu"
            self.state.gate_roi_enabled = self.gate_roi_enabled
            self.state.detection_roi_mode = self.detection_roi_mode
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

                roi = None
                # V0.5.14 decouples detection from counting geometry. The default
                # detector sees the full frame so a too-tight/misplaced Road Zone
                # cannot hide vehicles from YOLO/ByteTrack. Road Zone remains a
                # strict COUNTING guard only. Optional road/gate modes are kept
                # for low-power deployments.
                if self.detection_roi_mode == "road" and counter.road_zone is not None:
                    roi = road_zone_roi(counter.road_zone, width, height, margin_ratio=self.road_roi_margin)
                elif self.detection_roi_mode == "gate" and self.gate_roi_enabled:
                    roi = gate_roi_for_line(
                        counter.line,
                        width,
                        height,
                        margin_ratio=self.gate_roi_margin,
                        min_span_ratio=self.gate_roi_min_span,
                        endpoint_margin_ratio=self.gate_endpoint_margin,
                    )
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
                    agnostic_nms=self.agnostic_nms,
                    verbose=False,
                )
                self.state.inference_ms = round((time.perf_counter() - infer_started) * 1000.0, 1)
                result = results[0]

                crossing_this_frame = False
                pending_crossing_events: list[tuple[int, str, str, float, int, float | None, str | None, float | None, float | None]] = []
                refines_used_this_frame = 0
                boxes = result.boxes
                self.state.detections_current_frame = int(len(boxes)) if boxes is not None else 0
                self.state.active_tracks = 0
                self.state.untracked_detections = 0
                self.state.road_tracks_current_frame = 0
                self.state.suppressed_class_duplicates_current_frame = 0
                if boxes is not None and boxes.id is not None:
                    xyxy = boxes.xyxy.cpu().tolist()
                    ids = boxes.id.int().cpu().tolist()
                    classes = boxes.cls.int().cpu().tolist()
                    confs = boxes.conf.cpu().tolist()
                    labels = [str(result.names[int(cls_id)]) for cls_id in classes]
                    keep_indices, duplicate_aliases, suppressed_duplicates = single_heavy_vehicle_plan(
                        [tuple(map(float, rect)) for rect in xyxy],
                        labels,
                        [float(conf) for conf in confs],
                        self.heavy_duplicate_iou,
                    )
                    self.state.suppressed_class_duplicates_current_frame = suppressed_duplicates
                    # V0.5.30: cumulative telemetry counts unique raw-ID pairs,
                    # not the same overlapping CAR/TRUCK boxes once per frame.
                    # This turns values such as 2172 into an identity-fusion
                    # diagnostic instead of a misleading pseudo vehicle count.
                    for winner_index, duplicate_indices in duplicate_aliases.items():
                        winner_raw = int(ids[winner_index])
                        for duplicate_index in duplicate_indices:
                            duplicate_raw = int(ids[duplicate_index])
                            self._four_wheel_duplicate_pairs.add(tuple(sorted((winner_raw, duplicate_raw))))
                    self.state.four_wheel_duplicate_suppressed = len(self._four_wheel_duplicate_pairs)
                    claimed_canonical_ids: set[int] = set()
                    for item_index in keep_indices:
                        rect_roi = xyxy[item_index]
                        track_id_raw = ids[item_index]
                        cls_id = classes[item_index]
                        confidence = confs[item_index]
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
                        for duplicate_index in duplicate_aliases.get(item_index, []):
                            displaced = self._continuity.alias_raw_id(int(ids[duplicate_index]), track_id)
                            if displaced is not None:
                                self._merge_canonical_track_state(displaced, track_id, counter, heavy_rescuer)
                        if stitched:
                            self.state.stitch_recoveries = self._continuity.stitch_count
                            self.state.heavy_stitch_recoveries = self._continuity.heavy_stitch_count

                        velocity = self._continuity.velocity_for(track_id)
                        family_hint = vehicle_family(current_label)
                        anchor_inset = self.heavy_anchor_inset_ratio if family_hint == "four-wheel" else 0.0
                        anchor = motion_leading_anchor(rect, velocity, inset_ratio=anchor_inset)
                        if anchor_inset > 0.0 and int(track_id) not in self._heavy_anchor_tracks:
                            self._heavy_anchor_tracks.add(int(track_id))
                            self.state.heavy_anchor_tracks = len(self._heavy_anchor_tracks)
                        self.state.active_tracks += 1
                        if counter.road_zone is not None and counter.road_zone.contains(anchor, width, height):
                            self.state.road_tracks_current_frame += 1
                        self._seen_track_ids.add(track_id)
                        self._flow_calibrator.add(track_id, anchor, width, height, frame_index)
                        self._labels.update(track_id, current_label, confidence_f)
                        stable_label, class_certainty, class_hits = self._labels.stable_label(track_id, current_label)
                        base_display_label = self._class_policy.display_label(
                            current_label, stable_label, class_certainty, class_hits, confidence_f
                        )
                        self._refresh_truck_semantic_lock(
                            track_id, frame_index, stable_label, class_certainty, class_hits
                        )
                        display_label = base_display_label
                        cached_class = self._class_override_for(track_id, frame_index, base_display_label)
                        if cached_class is not None:
                            display_label = cached_class[0]

                        # V0.5.26 Target-aware Class Refiner 3.0. Heavy vehicles
                        # are rare enough to verify periodically even before they
                        # reach the gate, so the small delivery truck is shown as
                        # TRUCK instead of a permanent COCO `car`. Two-wheel
                        # tracks are refined only near the line to preserve FPS;
                        # this is where a bicycle/motorcycle mistake affects the
                        # persisted benchmark class.
                        line_a, line_b = counter.line.denormalize(width, height)
                        gate_distance_ratio = abs(signed_distance(anchor, line_a, line_b)) / max(1.0, min(width, height))
                        track_on_road = (
                            counter.road_zone is None
                            or counter.road_zone.contains_with_margin(anchor, width, height, 0.02)
                        )
                        lag_allows_class_refine = (
                            self.payload.source_type != "video"
                            or self.state.playback_lag_seconds <= self.refine_max_lag
                        )
                        family = vehicle_family(display_label)
                        pre_refine_candidate = track_on_road and (
                            family == "four-wheel"
                            or (family == "two-wheel" and gate_distance_ratio <= self.class_refine_gate_distance_ratio)
                        )
                        if (
                            self.refine_at_crossing
                            and pre_refine_candidate
                            and lag_allows_class_refine
                            and refines_used_this_frame < self.refine_max_per_frame
                        ):
                            class_refined, did_refine = self._observe_class_refiner(
                                track_id, frame_index, frame, rect, display_label, device, use_half, force=False
                            )
                            if did_refine:
                                refines_used_this_frame += 1
                            remembered = self._remember_class_refinement(
                                track_id, frame_index, current_label, stable_label, class_certainty,
                                class_hits, base_display_label, class_refined,
                            )
                            if remembered is not None:
                                display_label = remembered[0]

                        # V0.5.27 exposes detection-vs-count truth explicitly.
                        # Seeing a truck is not the same thing as counting one:
                        # only a truck track that later crosses the yellow line
                        # may increment counts_by_type["truck"].
                        locked_truck = self._truck_semantic_lock.resolve(track_id, frame_index, display_label)
                        if locked_truck is not None and int(track_id) not in self._truck_tracks_seen:
                            self._truck_tracks_seen.add(int(track_id))
                            self.state.truck_tracks_seen = len(self._truck_tracks_seen)
                        self.state.truck_semantic_locks = len(self._truck_tracks_seen)
                        if display_label == "bicycle" and int(track_id) not in self._bicycle_tracks_seen:
                            self._bicycle_tracks_seen.add(int(track_id))
                            self.state.bicycle_tracks_seen = len(self._bicycle_tracks_seen)

                        # V0.5.24 Rider-aware Human Guard 2.0 compatibility is preserved.
                        # V0.5.25 Transactional Human Guard 2.1.
                        # A pending two-wheel crossing is resolved on a *later*
                        # source frame before it is allowed into the DB. This also
                        # forces a quick follow-up observation instead of waiting
                        # the normal periodic interval.
                        buffered = self._pending_guard_crossings.get(track_id)
                        if buffered is not None:
                            action, _ = self._observe_human_guard(
                                track_id, frame_index, frame, rect, buffered.label, confidence_f,
                                device, use_half, velocity=velocity, force=True,
                            )
                            if action == "rejected":
                                self._drop_guard_crossing(counter, buffered)
                            elif action in {"rider", "released", "keep"}:
                                self._commit_guard_crossing(cv2, buffered)

                        # Rider-aware screening still runs periodically before the
                        # gate. _observe_human_guard caches same-frame results, so
                        # the crossing branch cannot accidentally turn one frame
                        # into two strikes.
                        suspect_human = (
                            display_label in TWO_WHEEL_LABELS
                            and is_person_like_two_wheel_box(rect)
                            and (counter.road_zone is None or counter.road_zone.contains_with_margin(anchor, width, height, 0.02))
                        )
                        if suspect_human and not self._human_guard_policy.is_rider(track_id):
                            self._observe_human_guard(
                                track_id, frame_index, frame, rect, display_label, confidence_f,
                                device, use_half, velocity=velocity, force=False,
                            )

                        heavy_center_candidate = None
                        if heavy_rescuer is not None and vehicle_family(display_label) == "four-wheel":
                            heavy_center_candidate = heavy_rescuer.update(
                                track_id, center, width, height, frame_index
                            )

                        direction = counter.update(
                            track_id, anchor, width, height, frame_index=frame_index,
                            origin_probe=(
                                center
                                if self.payload.source_type == "video" and frame_index <= self.video_origin_rescue_frames
                                else None
                            ),
                        )
                        if direction is None and heavy_center_candidate is not None:
                            heavy_direction, heavy_crossing_point = heavy_center_candidate
                            if counter.register_external_crossing(
                                track_id, heavy_direction, frame_index, heavy_crossing_point, mode="rescued"
                            ):
                                direction = heavy_direction
                                self._heavy_center_rescue_tracks.add(int(track_id))
                                self.state.heavy_center_rescues = len(self._heavy_center_rescue_tracks)
                        self.state.video_start_rescues = counter.origin_rescues
                        self.state.rejected_outside_road = counter.rejected_outside_road
                        self.state.fast_confirm_rescues = counter.fast_confirm_rescues
                        self.state.bracket_confirm_rescues = counter.bracket_confirm_rescues
                        self.state.rescue_validation_rejections = counter.rejected_rescue_validation
                        self.state.adaptive_cooldown_releases = counter.adaptive_cooldown_releases
                        guard_status = self._human_guard_policy.status(track_id)
                        overlay_label = "PERSON-GUARD" if guard_status == "rejected" else ("HUMAN?" if guard_status == "pending" else display_label)
                        self._draw_detection(
                            cv2,
                            frame,
                            rect,
                            track_id,
                            overlay_label,
                            confidence_f,
                            anchor,
                            class_certainty,
                            raw_track_id,
                        )

                        if direction:
                            crossing_this_frame = True
                            refined = None
                            lag_allows_refine = (
                                self.payload.source_type != "video"
                                or self.state.playback_lag_seconds <= self.refine_max_lag
                            )
                            # Reuse a same-frame pre-gate refinement first. If none
                            # exists, every supported vehicle class (including a
                            # high-certainty CAR) is eligible for target-aware
                            # crossing refinement. This is what lets best.pt rescue
                            # a small truck that the recall detector calls `car`.
                            cached_refine = self._class_refine_last_observation.get(int(track_id))
                            if cached_refine is not None and cached_refine[0] == int(frame_index):
                                refined = cached_refine[1]
                            elif (
                                self.refine_at_crossing
                                and display_label in AMBIGUOUS_CLASSES
                                and lag_allows_refine
                                and refines_used_this_frame < self.refine_max_per_frame
                            ):
                                refined, did_refine = self._observe_class_refiner(
                                    track_id, frame_index, frame, rect, display_label,
                                    device, use_half, force=True,
                                )
                                if did_refine:
                                    refines_used_this_frame += 1

                            if refined is None:
                                # A recent pre-gate class correction is still
                                # valid if the crossing frame cannot spend another
                                # refine slot. Treat it as cached semantic evidence.
                                cached_override = self._class_override_for(
                                    track_id, frame_index, base_display_label
                                )
                                if cached_override is not None:
                                    refined = cached_override

                            event_label, policy_conf = self._class_policy.final_label(
                                current_label,
                                stable_label,
                                class_certainty,
                                class_hits,
                                refined,
                            )
                            remembered = self._remember_class_refinement(
                                track_id, frame_index, current_label, stable_label, class_certainty,
                                class_hits, base_display_label, refined,
                            )
                            if remembered is not None:
                                event_label = remembered[0]
                                policy_conf = max(policy_conf, remembered[1])
                            event_label = event_label if event_label in VEHICLE_CLASSES else "other"
                            if event_label == "truck":
                                self._truck_tracks_seen.add(int(track_id))
                                self.state.truck_tracks_seen = len(self._truck_tracks_seen)
                                self._truck_crossing_tracks.add(int(track_id))
                                self.state.truck_crossing_tracks = len(self._truck_crossing_tracks)
                            elif event_label == "bicycle":
                                self._bicycle_tracks_seen.add(int(track_id))
                                self.state.bicycle_tracks_seen = len(self._bicycle_tracks_seen)
                            refined_conf = refined[1] if refined is not None else 0.0
                            event_confidence = max(confidence_f, policy_conf, refined_conf)

                            source_time_seconds = ((frame_index - 1) / self.state.source_fps) if self.state.source_fps > 0 else None
                            crossing_method = counter.crossing_mode_for(track_id)
                            crossing_point = counter.crossing_point_for(track_id)
                            crossing_x = (crossing_point[0] / width) if crossing_point is not None and width > 0 else None
                            crossing_y = (crossing_point[1] / height) if crossing_point is not None and height > 0 else None

                            if event_label in TWO_WHEEL_LABELS:
                                action, _ = self._observe_human_guard(
                                    track_id, frame_index, frame, rect, event_label, event_confidence,
                                    device, use_half, velocity=velocity, force=True,
                                )
                                if action == "rejected":
                                    counter.revoke_last_crossing(track_id, direction)
                                    self._draw_detection(
                                        cv2, frame, rect, track_id, "PERSON-GUARD", event_confidence,
                                        anchor, class_certainty, raw_track_id,
                                    )
                                    continue
                                if action == "pending":
                                    # Do not increment dashboard totals and do not
                                    # dispatch to backend yet. Keep the original
                                    # crossing frame/time/point in RAM; a later
                                    # distinct frame will COMMIT or DROP it.
                                    guard_snapshot = frame.copy()
                                    self._draw_overlay(cv2, guard_snapshot, counter)
                                    self._pending_guard_crossings[track_id] = _PendingGuardCrossing(
                                        track_id=track_id,
                                        label=event_label,
                                        direction=direction,
                                        confidence=event_confidence,
                                        frame_index=frame_index,
                                        source_time_seconds=source_time_seconds,
                                        crossing_method=crossing_method,
                                        crossing_x=crossing_x,
                                        crossing_y=crossing_y,
                                        snapshot_frame=guard_snapshot,
                                    )
                                    self.state.human_guard_pending_crossings = len(self._pending_guard_crossings)
                                    continue

                            self._record_committed_crossing(event_label, direction, crossing_method)
                            self.state.rejected_outside_road = counter.rejected_outside_road
                            pending_crossing_events.append((
                                track_id, event_label, direction, event_confidence, frame_index,
                                source_time_seconds, crossing_method, crossing_x, crossing_y,
                            ))
                elif boxes is not None and len(boxes) > 0:
                    # Ultralytics can return valid detections before ByteTrack confirms a
                    # persistent ID. Older builds hid these boxes completely because all
                    # drawing lived inside `boxes.id is not None`. Draw them now so DET>0
                    # is visually truthful, while still refusing to COUNT without a track.
                    xyxy = boxes.xyxy.cpu().tolist()
                    classes = boxes.cls.int().cpu().tolist()
                    confs = boxes.conf.cpu().tolist()
                    self.state.untracked_detections = len(xyxy)
                    for rect_roi, cls_id, confidence in zip(xyxy, classes, confs):
                        rx1, ry1, rx2, ry2 = rect_roi
                        rect = (rx1 + offset_x, ry1 + offset_y, rx2 + offset_x, ry2 + offset_y)
                        label = str(result.names[int(cls_id)])
                        self._draw_raw_detection(cv2, frame, rect, label, float(confidence))

                # Fail closed only for guard transactions that never receive a
                # second semantic observation (for example a track disappears
                # immediately after the line). Normal pending crossings resolve
                # on the very next distinct frame.
                expired_guard_crossings = [
                    pending for pending in self._pending_guard_crossings.values()
                    if frame_index - pending.frame_index >= self.human_guard_pending_max_frames
                ]
                for pending in expired_guard_crossings:
                    self._drop_guard_crossing(counter, pending, expired=True)

                calibration_stats = self._flow_calibrator.stats()
                self.state.calibration_samples = calibration_stats["sample_count"]
                self.state.calibration_tracks = calibration_stats["track_count"]
                self.state.calibration_moving_tracks = calibration_stats["moving_track_count"]
                self.state.calibration_ready = calibration_stats["ready"]
                if self.state.calibration_ready and (frame_index % 30 == 0 or self.state.calibration_proposal is None):
                    try:
                        cached_proposal = self._flow_calibrator.proposal()
                        cached_proposal["camera_id"] = self.payload.camera_id
                        cached_proposal["session_id"] = self.payload.session_id
                        self.state.calibration_proposal = cached_proposal
                        self.state.calibration_quality = float(cached_proposal.get("quality", 0.0))
                    except ValueError:
                        pass
                self.state.detected_tracks = len(self._seen_track_ids)
                self._draw_overlay(cv2, frame, counter)
                if trace_file is not None:
                    source_time = ((frame_index - 1) / self.state.source_fps) if self.state.source_fps > 0 else 0.0
                    trace_file.write(json.dumps({
                        "frame_index": frame_index,
                        "source_time_seconds": round(source_time, 4),
                        "detections": self.state.detections_current_frame,
                        "tracks": self.state.active_tracks,
                        "road_tracks": self.state.road_tracks_current_frame,
                        "untracked": self.state.untracked_detections,
                        "total_count": self.state.total_count,
                        "crossing_events": len(pending_crossing_events),
                        "rejected_outside_road": counter.rejected_outside_road,
                        "rejected_outside_segment": counter.rejected_outside_segment,
                        "rejected_unconfirmed_side": counter.rejected_unconfirmed_side,
                        "rejected_cooldown": counter.rejected_cooldown,
                        "road_edge_rescues": counter.road_edge_rescues,
                        "fast_confirm_rescues": counter.fast_confirm_rescues,
                        "bracket_confirm_rescues": counter.bracket_confirm_rescues,
                        "rescue_validation_rejections": counter.rejected_rescue_validation,
                        "adaptive_cooldown_releases": counter.adaptive_cooldown_releases,
                        "class_refine_checks": self.state.class_refine_checks,
                        "class_refine_target_matches": self.state.class_refine_target_matches,
                        "class_refine_target_rejects": self.state.class_refine_target_rejects,
                        "domain_refine_checks": self.state.domain_refine_checks,
                        "general_refine_checks": self.state.general_refine_checks,
                        "class_consensus_rescues": self.state.class_consensus_rescues,
                        "bicycle_class_rescues": self.state.bicycle_class_rescues,
                        "truck_class_rescues": self.state.truck_class_rescues,
                        "bicycle_tracks_seen": self.state.bicycle_tracks_seen,
                        "truck_tracks_seen": self.state.truck_tracks_seen,
                        "truck_crossing_tracks": self.state.truck_crossing_tracks,
                        "heavy_anchor_tracks": self.state.heavy_anchor_tracks,
                        "heavy_center_rescues": self.state.heavy_center_rescues,
                        "heavy_stitch_recoveries": self.state.heavy_stitch_recoveries,
                        "four_wheel_duplicate_suppressed": self.state.four_wheel_duplicate_suppressed,
                        "video_start_rescues": self.state.video_start_rescues,
                        "human_guard_rejections": self.state.human_guard_rejections,
                        "rider_guard_rescues": self.state.rider_guard_rescues,
                        "human_guard_pending_crossings": self.state.human_guard_pending_crossings,
                        "human_guard_deferred_commits": self.state.human_guard_deferred_commits,
                        "human_guard_pending_drops": self.state.human_guard_pending_drops,
                    }, separators=(",", ":")) + "\n")
                if pending_crossing_events:
                    snapshot = self._save_crossing_snapshot(cv2, frame, frame_index)
                    for event_track_id, event_label, event_direction, event_confidence, event_frame_index, event_source_time, event_method, event_crossing_x, event_crossing_y in pending_crossing_events:
                        self._event_dispatcher.submit(
                            self._event_payload(
                                event_track_id, event_label, event_direction, event_confidence, snapshot,
                                event_frame_index, event_source_time, event_method, event_crossing_x, event_crossing_y,
                            )
                        )
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
            # No ambiguous two-wheel crossing may leak into persistence at
            # shutdown. If the source ended before a second semantic frame,
            # revoke the provisional geometry crossing and record a timeout drop.
            if counter is not None and self._pending_guard_crossings:
                for pending in list(self._pending_guard_crossings.values()):
                    self._drop_guard_crossing(counter, pending, expired=True)
            if trace_file is not None:
                try:
                    trace_file.close()
                except Exception:
                    pass
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

    def _refine_crossing_label(self, frame, rect, device, use_half: bool, refine_ids: list[int], target_label: str | None = None, model=None) -> tuple[str, float] | None:
        """Refine the *tracked target*, never an arbitrary object in its crop.

        V0.5.25 selected the highest-confidence vehicle returned from the whole
        expanded crop. In the supplied benchmark frames that crop often contains
        roadside motorcycles next to the real bicycle or small truck. V0.5.26
        keeps a little context, then scores every refiner box against the original
        tracked rectangle and ignores unrelated neighbors.
        """
        active_model = model if model is not None else self._refiner_model
        if active_model is None or not refine_ids:
            return None
        try:
            h, w = frame.shape[:2]
            x1, y1, x2, y2 = [float(v) for v in rect]
            target_w = max(1.0, x2 - x1)
            target_h = max(1.0, y2 - y1)
            family = vehicle_family(target_label or "car")
            # Two-wheel targets need more vertical context for both wheels/rider;
            # four-wheel targets are kept tighter so adjacent parked motorcycles
            # cannot dominate the crop. The geometry matcher below is the final
            # authority, so these pads affect context rather than target identity.
            if family == "two-wheel":
                pad_x = max(14, int(target_w * 0.34))
                pad_y = max(14, int(target_h * 0.30))
            else:
                pad_x = max(12, int(target_w * 0.18))
                pad_y = max(12, int(target_h * 0.18))
            ix1 = max(0, int(x1) - pad_x)
            iy1 = max(0, int(y1) - pad_y)
            ix2 = min(w, int(x2) + pad_x)
            iy2 = min(h, int(y2) + pad_y)
            crop = frame[iy1:iy2, ix1:ix2]
            if crop.size == 0 or crop.shape[0] < 32 or crop.shape[1] < 32:
                return None
            predictions = active_model.predict(
                crop,
                conf=0.06,
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

            target_crop = (x1 - ix1, y1 - iy1, x2 - ix1, y2 - iy1)
            candidates: list[RefineCandidate] = []
            for box, cls_id, conf in zip(
                boxes.xyxy.cpu().tolist(),
                boxes.cls.int().cpu().tolist(),
                boxes.conf.cpu().tolist(),
            ):
                label = str(predictions[0].names[int(cls_id)])
                if label in VEHICLE_CLASSES:
                    candidates.append(RefineCandidate(label, float(conf), tuple(map(float, box))))
            match = select_target_refinement(
                target_crop,
                candidates,
                min_iou=self.refine_target_min_iou,
                min_target_coverage=self.refine_target_min_coverage,
                target_family=family,
            )
            if match is None:
                self.state.class_refine_target_rejects += 1
                return None
            self.state.class_refine_target_matches += 1
            return match.label, match.confidence
        except Exception:
            return None

    @staticmethod
    def _draw_raw_detection(cv2, frame, rect, label: str, confidence: float) -> None:
        x1, y1, x2, y2 = [int(v) for v in rect]
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 190, 255), 2)
        cv2.putText(
            frame,
            f"{label} DET {confidence:.2f}",
            (x1, max(18, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            (0, 190, 255),
            2,
        )

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
        import numpy as np
        h, w = frame.shape[:2]
        a, b = counter.line.denormalize(w, h)
        if counter.road_zone is not None:
            zone = np.array([[int(x), int(y)] for x, y in counter.road_zone.denormalize(w, h)], dtype=np.int32)
            overlay = frame.copy()
            cv2.fillPoly(overlay, [zone], (55, 190, 110))
            cv2.addWeighted(overlay, 0.12, frame, 0.88, 0, frame)
            cv2.polylines(frame, [zone], True, (55, 220, 130), 2)
            zx, zy = zone[0]
            cv2.putText(frame, "ROAD ZONE", (int(zx) + 8, max(24, int(zy) + 24)), cv2.FONT_HERSHEY_SIMPLEX, 0.56, (55, 220, 130), 2)
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
            f"DET {self.state.detections_current_frame} | UNTRACKED {self.state.untracked_detections} | TRACK {self.state.active_tracks} | ROAD {self.state.road_tracks_current_frame} | TOTAL {self.state.total_count} | IN {self.state.in_count} | OUT {self.state.out_count} | FPS {self.state.fps:.1f} ({rt}) | {self.state.inference_ms:.0f}ms | {'HYBRID' if self.hybrid_mode else 'DIRECT'} {Path(self.detector_model_name).name} | ROI {self.detection_roi_mode.upper()} | DIRECT-X {self.state.direct_crossings} | INTERP {self.state.interpolated_crossings} | RESCUE {self.state.rescued_crossings} | ROAD-REJECT {counter.rejected_outside_road} | CONFIRM-REJECT {counter.rejected_unconfirmed_side} | COOL-REJECT {counter.rejected_cooldown} | COOL-REL {counter.adaptive_cooldown_releases} | FAST-CONF {counter.fast_confirm_rescues} | BRACKET+ {counter.bracket_confirm_rescues} | RESCUE-X {counter.rejected_rescue_validation} | CLASS-R {self.state.class_refine_checks} | GEN-R {self.state.general_refine_checks} | CONS+ {self.state.class_consensus_rescues} | BIKE+ {self.state.bicycle_class_rescues} | TRUCK+ {self.state.truck_class_rescues} | TRUCK-SEEN {self.state.truck_tracks_seen} | TRUCK-X {self.state.truck_crossing_tracks} | HEAVY-A {self.state.heavy_anchor_tracks} | HEAVY-C+ {self.state.heavy_center_rescues} | HEAVY-STITCH {self.state.heavy_stitch_recoveries} | 4W-DUP {self.state.four_wheel_duplicate_suppressed} | START+ {self.state.video_start_rescues} | HUMAN-X {self.state.human_guard_rejections} | RIDER+ {self.state.rider_guard_rescues} | GUARD-PENDING {self.state.human_guard_pending_crossings} | ROAD-EDGE+ {counter.road_edge_rescues}",
            (20, 32),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (0, 200, 255),
            2,
        )
        if self.state.pending_events:
            cv2.putText(frame, f"DB QUEUE {self.state.pending_events}", (20, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 165, 255), 2)

    def _save_crossing_snapshot(self, cv2, frame, frame_index: int) -> str | None:
        """Write one snapshot per crossing frame, even if many vehicles cross together."""
        try:
            folder = self.snapshot_root / f"camera_{self.payload.camera_id}"
            folder.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            path = folder / f"{stamp}_frame_{frame_index}.jpg"
            cv2.imwrite(str(path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
            return str(path.relative_to(self.snapshot_root)).replace("\\", "/")
        except Exception:
            return None

    def _event_payload(self, track_id: int, label: str, direction: str, confidence: float, snapshot: str | None, source_frame_index: int | None = None, source_time_seconds: float | None = None, crossing_method: str | None = None, crossing_x: float | None = None, crossing_y: float | None = None) -> dict:
        return {
            "camera_id": self.payload.camera_id,
            "session_id": self.payload.session_id,
            "model_id": self.payload.model_id,
            "tracking_id": track_id,
            "vehicle_type": label if label in VEHICLE_CLASSES else "other",
            "direction": direction,
            "confidence": confidence,
            "snapshot_path": snapshot,
            "source_frame_index": source_frame_index,
            "source_time_seconds": round(float(source_time_seconds), 4) if source_time_seconds is not None else None,
            "crossing_method": crossing_method,
            "crossing_x": round(float(crossing_x), 6) if crossing_x is not None else None,
            "crossing_y": round(float(crossing_y), 6) if crossing_y is not None else None,
        }

    def _notify_finished(self) -> None:
        payload = {
            "status": self.state.status,
            "total_vehicles": self.state.total_count,
            "average_fps": self.state.fps,
            "human_guard_rejections": self.state.human_guard_rejections,
            "source_fps": self.state.source_fps or None,
            "source_duration_seconds": self.state.source_duration_seconds or None,
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
                try:
                    result = response.json()
                    self.state.persisted_events = int(result.get("persisted_events", self.state.persisted_events))
                    self.state.deduplicated_events = int(result.get("dedup_suppressed_events", self.state.deduplicated_events))
                    # Once the session is closed, make the dashboard counters
                    # reflect durable DB truth instead of pre-dedup worker candidates.
                    if "persisted_events" in result:
                        self.state.total_count = int(result.get("persisted_events", self.state.total_count))
                        self.state.in_count = int(result.get("persisted_in", self.state.in_count))
                        self.state.out_count = int(result.get("persisted_out", self.state.out_count))
                        counts = result.get("persisted_by_type")
                        if isinstance(counts, dict):
                            self.state.counts_by_type = {key: int(counts.get(key, 0)) for key in self.state.counts_by_type}
                except Exception:
                    pass
                return
            except Exception as exc:
                self.state.last_error = f"Session finish notification attempt {attempt} failed: {exc}"
                if attempt < 6:
                    time.sleep(0.35 * attempt)
