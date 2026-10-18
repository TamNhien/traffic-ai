"""V0.5.100: tightly scoped same-raw-token double-crossing protection.

ByteTrack may briefly assign raw token R to canonical A, then to canonical B
while both canonical tracks are visible. Only a very recent and geometrically
consistent transfer of the SAME raw token may suppress B's second passage.
Time/box proximity alone is intentionally insufficient: convoys must count.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

Rect = tuple[float, float, float, float]


def _iou(a: Rect, b: Rect) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    aa = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    bb = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    overlap = ix * iy
    return overlap / (aa + bb - overlap) if aa + bb > overlap else 0.0


@dataclass(frozen=True, slots=True)
class _Observation:
    owner: int
    frame: int
    rect: Rect


@dataclass(frozen=True, slots=True)
class _Handoff:
    former_owner: int
    frame: int
    overlap: float


@dataclass(frozen=True, slots=True)
class _Passage:
    owner: int
    frame: int
    direction: str
    x: float
    y: float


class RawHandoffCrossingGuard:
    """Suppress only same-direction duplicate passage proven by raw handoff.

    Causal by design: never inspect future images, GT labels, backend matcher
    results, or session-specific track IDs. State is bounded and expires.
    """

    def __init__(self, *, max_handoff_gap: int = 3, max_passage_age: int = 12,
                 max_event_age: int = 10, min_handoff_iou: float = 0.64,
                 max_crossing_dx: float = 0.025, max_crossing_dy: float = 0.018):
        self.max_handoff_gap = max_handoff_gap
        self.max_passage_age = max_passage_age
        self.max_event_age = max_event_age
        self.min_handoff_iou = min_handoff_iou
        self.max_crossing_dx = max_crossing_dx
        self.max_crossing_dy = max_crossing_dy
        self._last: dict[int, _Observation] = {}
        self._handoffs: dict[tuple[int, int], _Handoff] = {}
        self._passages: dict[int, _Passage] = {}
        self.suppressed = 0
        self._last_cleanup_frame = -1

    def _cleanup(self, frame: int) -> None:
        if frame - self._last_cleanup_frame < 25:
            return
        self._last_cleanup_frame = frame
        self._last = {k: v for k, v in self._last.items() if frame - v.frame <= 25}
        self._handoffs = {k: v for k, v in self._handoffs.items() if frame - v.frame <= self.max_event_age}
        self._passages = {k: v for k, v in self._passages.items() if frame - v.frame <= self.max_passage_age}
        # A pathological source cannot retain unlimited unique IDs between
        # cleanups; the next cleanup will retain only the last 25 frame records.

    def observe(self, raw_id: int, canonical_id: int, frame: int, rect: Rect) -> None:
        raw_id, canonical_id, frame = int(raw_id), int(canonical_id), int(frame)
        self._cleanup(frame)
        if len(rect) != 4 or not all(isfinite(float(v)) for v in rect):
            return
        converted = tuple(float(v) for v in rect)
        if converted[2] <= converted[0] or converted[3] <= converted[1]:
            return
        old = self._last.get(raw_id)
        if old and old.owner != canonical_id:
            gap = frame - old.frame
            overlap = _iou(old.rect, converted)
            if 0 < gap <= self.max_handoff_gap and overlap >= self.min_handoff_iou:
                self._handoffs[(raw_id, canonical_id)] = _Handoff(old.owner, frame, overlap)
        if old is None or frame >= old.frame:
            self._last[raw_id] = _Observation(canonical_id, frame, converted)

    def note_passage(self, canonical_id: int, frame: int, direction: str,
                     crossing_x: float | None, crossing_y: float | None) -> None:
        if direction not in {'in', 'out'} or crossing_x is None or crossing_y is None:
            return
        if not all(isfinite(float(v)) and 0 <= float(v) <= 1 for v in (crossing_x, crossing_y)):
            return
        self._cleanup(int(frame))
        self._passages[int(canonical_id)] = _Passage(int(canonical_id), int(frame), direction,
                                                    float(crossing_x), float(crossing_y))

    def duplicate_of(self, raw_id: int, canonical_id: int, frame: int, direction: str,
                     crossing_x: float | None, crossing_y: float | None,
                     *, crossing_method: str | None) -> dict | None:
        """Return finite, auditable suppression proof, or None (fail open)."""
        if crossing_method != 'direct' or direction not in ('in', 'out'):
            return None
        if crossing_x is None or crossing_y is None:
            return None
        if not all(isfinite(float(v)) and 0 <= float(v) <= 1 for v in (crossing_x, crossing_y)):
            return None
        frame, raw_id, canonical_id = int(frame), int(raw_id), int(canonical_id)
        self._cleanup(frame)
        link = self._handoffs.get((raw_id, canonical_id))
        if link is None or not (0 <= frame - link.frame <= self.max_event_age):
            return None
        if link.former_owner == canonical_id:
            return None
        first = self._passages.get(link.former_owner)
        if first is None or first.direction != direction or not (0 < frame - first.frame <= self.max_passage_age):
            return None
        if abs(float(crossing_x) - first.x) > self.max_crossing_dx or \
           abs(float(crossing_y) - first.y) > self.max_crossing_dy:
            return None
        self.suppressed += 1
        # Consume transfer so the same link cannot suppress another passage.
        self._handoffs.pop((raw_id, canonical_id), None)
        return {
            'kind': 'verified_raw_handoff_duplicate',
            'former_canonical_id': first.owner, 'current_canonical_id': canonical_id,
            'shared_raw_track_id': raw_id, 'handoff_frame': link.frame,
            'frame_delta': frame - first.frame,
            'handoff_box_iou': round(link.overlap, 4),
            'crossing_dx': round(abs(float(crossing_x) - first.x), 6),
            'crossing_dy': round(abs(float(crossing_y) - first.y), 6),
            'direction': direction,
        }
