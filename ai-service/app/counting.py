from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from math import hypot

Point = tuple[float, float]


@dataclass(slots=True)
class CountingLine:
    x1: float = 0.1
    y1: float = 0.5
    x2: float = 0.9
    y2: float = 0.5

    def denormalize(self, width: int, height: int) -> tuple[Point, Point]:
        return (self.x1 * width, self.y1 * height), (self.x2 * width, self.y2 * height)


def signed_side(point: Point, a: Point, b: Point) -> float:
    return (b[0] - a[0]) * (point[1] - a[1]) - (b[1] - a[1]) * (point[0] - a[0])


def signed_distance(point: Point, a: Point, b: Point) -> float:
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    length = max((dx * dx + dy * dy) ** 0.5, 1e-9)
    return signed_side(point, a, b) / length


def _orientation(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def segments_intersect(a: Point, b: Point, c: Point, d: Point, eps: float = 1e-6) -> bool:
    o1 = _orientation(a, b, c)
    o2 = _orientation(a, b, d)
    o3 = _orientation(c, d, a)
    o4 = _orientation(c, d, b)
    return (o1 * o2 <= eps) and (o3 * o4 <= eps)


@dataclass(slots=True)
class _GateSample:
    frame_index: int
    point: Point
    distance: float
    side: int


@dataclass(slots=True)
class _TrackGateState:
    history: deque[_GateSample] = field(default_factory=lambda: deque(maxlen=32))
    armed: bool = True
    counted_directions: set[str] = field(default_factory=set)
    last_count_frame: int = -10_000


class LineCrossingCounter:
    """Trajectory-based bidirectional virtual gate.

    Smart Gate 4.0 does not require the crossing to happen in two adjacent
    frames. It keeps a bounded trajectory history and can confirm a finite-line
    crossing across short detector/tracker gaps. A crossing is accepted only if
    the trajectory really intersects the counting segment and contains enough
    motion perpendicular to the gate, which suppresses vehicles travelling
    parallel to the line or jittering on it.
    """

    def __init__(
        self,
        line: CountingLine,
        segment_margin: float = 0.08,
        dead_band_ratio: float = 0.008,
        rearm_distance_ratio: float = 0.030,
        history_gap_frames: int = 30,
        min_perpendicular_ratio: float = 0.12,
        min_crossing_motion_ratio: float = 0.006,
    ) -> None:
        self.line = line
        self.segment_margin = max(0.0, float(segment_margin))
        self.dead_band_ratio = max(0.0, float(dead_band_ratio))
        self.rearm_distance_ratio = max(self.dead_band_ratio, float(rearm_distance_ratio))
        self.history_gap_frames = max(2, int(history_gap_frames))
        self.min_perpendicular_ratio = max(0.0, min(1.0, float(min_perpendicular_ratio)))
        self.min_crossing_motion_ratio = max(0.0, float(min_crossing_motion_ratio))
        self._tracks: dict[int, _TrackGateState] = {}
        self.in_count = 0
        self.out_count = 0
        self.rescued_crossings = 0

    def update(
        self,
        track_id: int,
        anchor: Point,
        frame_width: int,
        frame_height: int,
        frame_index: int | None = None,
    ) -> str | None:
        if frame_index is None:
            state_existing = self._tracks.get(track_id)
            frame_index = (state_existing.history[-1].frame_index + 1) if state_existing and state_existing.history else 1

        a, b = self.line.denormalize(frame_width, frame_height)
        distance = signed_distance(anchor, a, b)
        dead_band = max(3.0, frame_height * self.dead_band_ratio)
        rearm_distance = max(dead_band * 2.0, frame_height * self.rearm_distance_ratio)
        side = 0 if abs(distance) <= dead_band else (1 if distance > 0 else -1)

        state = self._tracks.setdefault(int(track_id), _TrackGateState())
        sample = _GateSample(int(frame_index), anchor, distance, side)

        # After a valid crossing, the track must move away from the line before a
        # reverse traversal is accepted. This avoids double-counts from box jitter.
        if not state.armed:
            state.history.append(sample)
            if abs(distance) >= rearm_distance:
                state.armed = True
                # Keep only recent samples after re-arming so an old point from the
                # previous traversal cannot be paired with the next crossing.
                state.history = deque(list(state.history)[-4:], maxlen=32)
            return None

        state.history.append(sample)
        if side == 0:
            return None

        # Search backwards for the nearest stable sample on the opposite side.
        # This rescues crossings across several missed detections / ID stitching
        # frames instead of only comparing the immediately previous frame.
        previous: _GateSample | None = None
        for candidate in reversed(list(state.history)[:-1]):
            gap = sample.frame_index - candidate.frame_index
            if gap <= 0:
                continue
            if gap > self.history_gap_frames:
                break
            if candidate.side == -side:
                previous = candidate
                break

        if previous is None:
            return None

        dx = b[0] - a[0]
        dy = b[1] - a[1]
        a_ext = (a[0] - dx * self.segment_margin, a[1] - dy * self.segment_margin)
        b_ext = (b[0] + dx * self.segment_margin, b[1] + dy * self.segment_margin)
        if not segments_intersect(previous.point, anchor, a_ext, b_ext):
            return None

        move_x = anchor[0] - previous.point[0]
        move_y = anchor[1] - previous.point[1]
        move_len = max(hypot(move_x, move_y), 1e-6)
        perpendicular = abs(distance - previous.distance)
        min_motion = max(3.0, frame_height * self.min_crossing_motion_ratio)
        if perpendicular < min_motion:
            return None
        if perpendicular / move_len < self.min_perpendicular_ratio:
            return None

        direction = "in" if previous.side < 0 < side else "out"
        if direction in state.counted_directions:
            return None

        state.counted_directions.add(direction)
        state.armed = False
        state.last_count_frame = sample.frame_index
        gap = sample.frame_index - previous.frame_index
        if gap > 1:
            self.rescued_crossings += 1
        state.history = deque([sample], maxlen=32)

        if direction == "in":
            self.in_count += 1
        else:
            self.out_count += 1
        return direction

    @property
    def counted_tracks(self) -> int:
        return sum(1 for state in self._tracks.values() if state.counted_directions)

    @property
    def total_crossings(self) -> int:
        return self.in_count + self.out_count
