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


def _cross(v1: Point, v2: Point) -> float:
    return v1[0] * v2[1] - v1[1] * v2[0]


def segment_crossing_point(
    p0: Point,
    p1: Point,
    a: Point,
    b: Point,
    segment_margin: float = 0.0,
    eps: float = 1e-7,
) -> Point | None:
    """Return the finite-gate intersection for a trajectory segment.

    `segment_margin` is expressed as a fraction of the visible counting-line
    length. V0.5.8 uses zero margin by default, so a vehicle is never counted
    merely because its trajectory crosses an imaginary extension beyond either
    endpoint of the line.
    """

    r = (p1[0] - p0[0], p1[1] - p0[1])
    s = (b[0] - a[0], b[1] - a[1])
    denominator = _cross(r, s)
    if abs(denominator) <= eps:
        return None

    q_minus_p = (a[0] - p0[0], a[1] - p0[1])
    t = _cross(q_minus_p, s) / denominator
    u = _cross(q_minus_p, r) / denominator
    margin = max(0.0, float(segment_margin))
    if t < -eps or t > 1.0 + eps:
        return None
    if u < -margin - eps or u > 1.0 + margin + eps:
        return None
    return (p0[0] + t * r[0], p0[1] + t * r[1])


def segments_intersect(a: Point, b: Point, c: Point, d: Point, eps: float = 1e-6) -> bool:
    return segment_crossing_point(a, b, c, d, segment_margin=0.0, eps=eps) is not None


@dataclass(slots=True)
class _GateSample:
    frame_index: int
    point: Point
    distance: float
    side: int


@dataclass(slots=True)
class _TrackGateState:
    history: deque[_GateSample] = field(default_factory=lambda: deque(maxlen=48))
    armed: bool = True
    counted_directions: set[str] = field(default_factory=set)
    last_count_frame: int = -10_000


class LineCrossingCounter:
    """Strict finite-line, trajectory-based bidirectional virtual gate.

    The counter keeps a bounded trajectory history so fast vehicles can still be
    counted when detector/tracker observations are missing for several frames.
    A crossing is accepted only when the trajectory intersects the *visible*
    counting segment, not an infinite line, and when enough motion is normal to
    the gate. This suppresses roadside/sidewalk traffic and line-parallel jitter.
    """

    def __init__(
        self,
        line: CountingLine,
        segment_margin: float = 0.0,
        dead_band_ratio: float = 0.006,
        rearm_distance_ratio: float = 0.028,
        history_gap_frames: int = 45,
        min_perpendicular_ratio: float = 0.10,
        min_crossing_motion_ratio: float = 0.004,
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
        self.rejected_outside_segment = 0

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
        scale = max(1.0, min(frame_width, frame_height))
        dead_band = max(2.0, scale * self.dead_band_ratio)
        rearm_distance = max(dead_band * 2.0, scale * self.rearm_distance_ratio)
        side = 0 if abs(distance) <= dead_band else (1 if distance > 0 else -1)

        state = self._tracks.setdefault(int(track_id), _TrackGateState())
        sample = _GateSample(int(frame_index), anchor, distance, side)

        if not state.armed:
            state.history.append(sample)
            if abs(distance) >= rearm_distance:
                state.armed = True
                state.history = deque(list(state.history)[-5:], maxlen=48)
            return None

        state.history.append(sample)
        if side == 0:
            return None

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

        crossing = segment_crossing_point(
            previous.point,
            anchor,
            a,
            b,
            segment_margin=self.segment_margin,
        )
        if crossing is None:
            self.rejected_outside_segment += 1
            return None

        move_x = anchor[0] - previous.point[0]
        move_y = anchor[1] - previous.point[1]
        move_len = max(hypot(move_x, move_y), 1e-6)
        perpendicular = abs(distance - previous.distance)
        min_motion = max(2.0, scale * self.min_crossing_motion_ratio)
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
        state.history = deque([sample], maxlen=48)

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
