from __future__ import annotations

import queue
import threading
import time
from typing import Callable

import httpx2 as httpx


class LatestFrameEncoder(threading.Thread):
    def __init__(self, on_jpeg: Callable[[bytes], None], state, quality: int = 72, max_width: int = 960) -> None:
        super().__init__(daemon=True, name="traffic-ai-jpeg")
        self.on_jpeg = on_jpeg
        self.state = state
        self.quality = int(quality)
        self.max_width = int(max_width)
        self._queue: queue.Queue = queue.Queue(maxsize=1)
        self._stop_event = threading.Event()

    def submit(self, frame) -> None:
        if self._stop_event.is_set():
            return
        try:
            self._queue.put_nowait(frame.copy())
        except queue.Full:
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except queue.Empty:
                pass
            self.state.stream_frames_dropped += 1
            try:
                self._queue.put_nowait(frame.copy())
            except queue.Full:
                self.state.stream_frames_dropped += 1

    def stop_and_join(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        self.join(timeout=timeout)

    def run(self) -> None:
        import cv2
        while not self._stop_event.is_set() or not self._queue.empty():
            try:
                frame = self._queue.get(timeout=0.15)
            except queue.Empty:
                continue
            try:
                stream_frame = frame
                if self.max_width > 0 and frame.shape[1] > self.max_width:
                    scale = self.max_width / float(frame.shape[1])
                    stream_frame = cv2.resize(
                        frame,
                        (self.max_width, max(2, int(round(frame.shape[0] * scale)))),
                        interpolation=cv2.INTER_AREA,
                    )
                ok, encoded = cv2.imencode(".jpg", stream_frame, [int(cv2.IMWRITE_JPEG_QUALITY), self.quality])
                if ok:
                    self.on_jpeg(encoded.tobytes())
                    self.state.stream_frames_encoded += 1
            finally:
                self._queue.task_done()


class EventDispatcher(threading.Thread):
    def __init__(self, backend_url: str, token: str, state, max_queue: int = 512) -> None:
        super().__init__(daemon=True, name="traffic-ai-events")
        self.backend_url = backend_url.rstrip("/")
        self.token = token
        self.state = state
        self._queue: queue.Queue[dict] = queue.Queue(maxsize=max_queue)
        self._stop_event = threading.Event()

    def submit(self, payload: dict) -> None:
        try:
            self._queue.put(payload, timeout=1.0)
            self.state.pending_events = self._queue.qsize()
        except queue.Full as exc:
            self.state.delivery_failures += 1
            self.state.last_error = "Event queue full; backend persistence is too slow"
            raise RuntimeError(self.state.last_error) from exc

    def stop_and_flush(self, timeout: float = 20.0) -> None:
        deadline = time.monotonic() + timeout
        while not self._queue.empty() and time.monotonic() < deadline:
            time.sleep(0.05)
        self._stop_event.set()
        self.join(timeout=max(1.0, deadline - time.monotonic()))

    def run(self) -> None:
        with httpx.Client(headers={"X-AI-Token": self.token}, timeout=4.0) as client:
            while not self._stop_event.is_set() or not self._queue.empty():
                try:
                    payload = self._queue.get(timeout=0.15)
                except queue.Empty:
                    continue
                delivered = False
                try:
                    for attempt in range(1, 6):
                        try:
                            response = client.post(f"{self.backend_url}/events", json=payload)
                            response.raise_for_status()
                            self.state.delivered_events += 1
                            delivered = True
                            break
                        except Exception as exc:
                            self.state.delivery_failures += 1
                            self.state.last_error = f"Event delivery attempt {attempt} failed: {exc}"
                            if attempt < 5:
                                time.sleep(min(1.0, 0.12 * attempt))
                    if delivered and self.state.last_error and self.state.last_error.startswith("Event delivery attempt"):
                        self.state.last_error = None
                finally:
                    self._queue.task_done()
                    self.state.pending_events = self._queue.qsize()
