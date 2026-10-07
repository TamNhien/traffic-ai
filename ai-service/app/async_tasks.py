from __future__ import annotations

import queue
import threading
import time
from typing import Callable

import httpx2 as httpx


DELIVERY_AUDIT_PAYLOAD_FIELDS = (
    "camera_id", "session_id", "tracking_id", "vehicle_type", "direction",
    "confidence", "source_frame_index", "source_time_seconds", "crossing_method",
    "crossing_x", "crossing_y",
)
DELIVERY_AUDIT_DEDUP_REASONS = frozenset({
    "same-track-delivery-retry", "same-track-repeat-jitter", "same-track-direction-flip",
    "startup-crossing-signature", "crossing-signature", "two-wheel-rescue-signature",
    "two-wheel-spatial-signature", "two-wheel-ultra-spatial-signature",
    "secondary-shadow-signature", "secondary-reverse-shadow", "direct-ultra-shadow",
    "direct-secondary-shadow", "semantic-family-shadow", "semantic-family-reverse-shadow",
    "heavy-semantic-signature",
})


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
        self._admission_lock = threading.Lock()
        # V0.5.63: acknowledgments belong to the submitted source event. The
        # worker drains this bounded queue through its sole trace writer; the
        # delivery thread never writes a trace or waits for audit consumers.
        self._delivery_audits: queue.Queue[dict] = queue.Queue(maxsize=1024)
        self.delivery_audit_dropped = 0

    def _record_delivery_audit(self, payload: dict, response, attempts: int, delivered: bool) -> None:
        record = {key: payload[key] for key in DELIVERY_AUDIT_PAYLOAD_FIELDS if key in payload}
        outcome, backend_event_id, dedup_reason = "failed", None, None
        if delivered:
            deduplicated = response.headers.get("X-TrafficAI-Deduplicated")
            outcome = {"0": "created", "1": "deduplicated"}.get(deduplicated, "acknowledged_unknown")
            if outcome == "deduplicated":
                reason = response.headers.get("X-TrafficAI-Dedup-Reason")
                if reason in DELIVERY_AUDIT_DEDUP_REASONS:
                    dedup_reason = reason
            try:
                body = response.json()
                event_id = body.get("id") if isinstance(body, dict) else None
                if isinstance(event_id, int) and not isinstance(event_id, bool) and event_id > 0:
                    backend_event_id = event_id
            except Exception:
                # Legacy/header-only or malformed response bodies cannot turn
                # an already acknowledged event into another HTTP attempt.
                pass
        record.update(
            kind="event_delivery", audit_only=True,
            stage="backend_acknowledged" if delivered else "delivery_failed",
            outcome=outcome, attempts=int(attempts), backend_event_id=backend_event_id,
            dedup_reason=dedup_reason,
        )
        self._delivery_audits.put_nowait(record)

    def drain_delivery_audits(self) -> list[dict]:
        records = []
        while True:
            try:
                records.append(self._delivery_audits.get_nowait())
            except queue.Empty:
                return records
            self._delivery_audits.task_done()

    def _refresh_pending_events(self) -> int:
        # qsize excludes the request currently being retried. Accepted work
        # stays pending until its final attempt reaches task_done().
        with self._queue.mutex:
            pending = self._queue.unfinished_tasks
            self.state.pending_events = pending
            return pending

    def submit(self, payload: dict) -> None:
        # Once shutdown closes admission, a producer cannot enqueue work
        # behind the consumer's final empty-queue check.
        with self._admission_lock:
            if self._stop_event.is_set():
                raise RuntimeError("Event dispatcher is stopping; event was not accepted")
            try:
                self._queue.put(payload, timeout=1.0)
                self._refresh_pending_events()
            except queue.Full as exc:
                self.state.delivery_failures += 1
                self.state.last_error = "Event queue full; backend persistence is too slow"
                raise RuntimeError(self.state.last_error) from exc

    def stop_and_flush(self, timeout: float | None = 20.0) -> bool:
        """Close admission and report whether all accepted work terminated.

        A bounded caller may time out while a request is in flight; that is
        not a successful flush. The worker uses None so session finish follows
        the existing finite delivery retry policy for every accepted event.
        """
        with self._admission_lock:
            self._stop_event.set()
        if self.ident is not None:
            self.join(timeout=None if timeout is None else max(0.0, float(timeout)))
        pending = self._refresh_pending_events()
        return not self.is_alive() and pending == 0

    def run(self) -> None:
        with httpx.Client(headers={"X-AI-Token": self.token}, timeout=4.0) as client:
            while not self._stop_event.is_set() or not self._queue.empty():
                try:
                    payload = self._queue.get(timeout=0.15)
                except queue.Empty:
                    continue
                delivered = False
                response = None
                try:
                    for attempt in range(1, 6):
                        try:
                            response = client.post(f"{self.backend_url}/events", json=payload)
                            response.raise_for_status()
                            self.state.delivered_events += 1
                            if response.headers.get("X-TrafficAI-Deduplicated") == "1":
                                self.state.deduplicated_events += 1
                                dedup_reason = response.headers.get("X-TrafficAI-Dedup-Reason")
                                if dedup_reason == "crossing-signature":
                                    self.state.crossing_signature_duplicates += 1
                                elif dedup_reason == "two-wheel-rescue-signature":
                                    self.state.two_wheel_signature_duplicates += 1
                                elif dedup_reason == "two-wheel-spatial-signature":
                                    self.state.two_wheel_signature_duplicates += 1
                                    self.state.two_wheel_spatial_signature_duplicates += 1
                                elif dedup_reason == "two-wheel-ultra-spatial-signature":
                                    self.state.two_wheel_signature_duplicates += 1
                                    self.state.two_wheel_spatial_signature_duplicates += 1
                                    self.state.two_wheel_ultra_spatial_signature_duplicates += 1
                                elif dedup_reason == "same-track-repeat-jitter":
                                    self.state.same_track_repeat_duplicates += 1
                                elif dedup_reason == "same-track-direction-flip":
                                    self.state.direction_flip_duplicates += 1
                                elif dedup_reason == "secondary-shadow-signature":
                                    self.state.secondary_shadow_duplicates += 1
                                elif dedup_reason == "direct-ultra-shadow":
                                    self.state.direct_shadow_duplicates += 1
                                elif dedup_reason == "direct-secondary-shadow":
                                    self.state.cross_method_shadow_duplicates += 1
                                elif dedup_reason in {"semantic-family-shadow", "semantic-family-reverse-shadow"}:
                                    self.state.semantic_shadow_duplicates += 1
                                    if dedup_reason == "semantic-family-reverse-shadow":
                                        self.state.reverse_shadow_duplicates += 1
                                elif dedup_reason == "secondary-reverse-shadow":
                                    self.state.reverse_shadow_duplicates += 1
                            else:
                                self.state.persisted_events += 1
                            delivered = True
                            break
                        except Exception as exc:
                            self.state.delivery_failures += 1
                            self.state.last_error = f"Event delivery attempt {attempt} failed: {exc}"
                            if attempt < 5:
                                time.sleep(min(1.0, 0.12 * attempt))
                    if delivered and self.state.last_error and self.state.last_error.startswith("Event delivery attempt"):
                        self.state.last_error = None
                    # Emit one terminal audit after the finite retry policy.
                    # Audit failures are isolated from delivery: retrying here
                    # would resend an event the backend already acknowledged.
                    try:
                        self._record_delivery_audit(payload, response, attempt, delivered)
                    except Exception:
                        self.delivery_audit_dropped += 1
                finally:
                    self._queue.task_done()
                    self._refresh_pending_events()
