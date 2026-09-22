from __future__ import annotations

import threading
from dataclasses import asdict, dataclass
from typing import Any

from app.schemas import PipelineStart


@dataclass(slots=True)
class PipelineState:
    camera_id: int
    session_id: int
    status: str = "starting"
    fps: float = 0.0
    inference_ms: float = 0.0
    processed_frames: int = 0
    total_count: int = 0
    in_count: int = 0
    out_count: int = 0
    detected_tracks: int = 0
    delivered_events: int = 0
    pending_events: int = 0
    delivery_failures: int = 0
    model_name: str | None = None
    imgsz: int | None = None
    half_precision: bool = False
    frame_width: int | None = None
    frame_height: int | None = None
    last_error: str | None = None


class PipelineRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._workers: dict[int, Any] = {}
        self._states: dict[int, PipelineState] = {}

    def start(self, payload: PipelineStart) -> dict:
        with self._lock:
            existing = self._workers.get(payload.camera_id)
            if existing is not None and existing.is_alive():
                raise ValueError("Pipeline already running for this camera")
            self._workers.pop(payload.camera_id, None)
            from app.worker import PipelineWorker

            state = PipelineState(camera_id=payload.camera_id, session_id=payload.session_id)
            worker = PipelineWorker(payload=payload, state=state, on_finished=self._on_finished)
            self._workers[payload.camera_id] = worker
            self._states[payload.camera_id] = state
            worker.start()
            return asdict(state)

    def stop(self, camera_id: int) -> dict:
        with self._lock:
            worker = self._workers.get(camera_id)
            state = self._states.get(camera_id)
        if worker is None or state is None:
            raise KeyError(camera_id)
        worker.stop()
        worker.join(timeout=15)
        return asdict(state)

    def list(self) -> list[dict]:
        with self._lock:
            return [asdict(state) for state in self._states.values()]

    def get(self, camera_id: int) -> dict:
        with self._lock:
            state = self._states.get(camera_id)
            if state is None:
                raise KeyError(camera_id)
            return asdict(state)

    def latest_jpeg(self, camera_id: int) -> bytes | None:
        with self._lock:
            worker = self._workers.get(camera_id)
        return None if worker is None else worker.latest_jpeg

    def _on_finished(self, camera_id: int) -> None:
        with self._lock:
            self._workers.pop(camera_id, None)


registry = PipelineRegistry()
