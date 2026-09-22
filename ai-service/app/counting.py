from __future__ import annotations

from dataclasses import dataclass, field

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
    """Signed perpendicular distance from ``point`` to the infinite line AB."""
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    length = max((dx * dx + dy * dy) ** 0.5, 1e-9)
    return signed_side(point, a, b) / length


def projection_parameter(point: Point, a: Point, b: Point) -> float:
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    denom = dx * dx + dy * dy
    if denom <= 1e-9:
        return 0.0
    return ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / denom


def _orientation(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def segments_intersect(a: Point, b: Point, c: Point, d: Point, eps: float = 1e-6) -> bool:
    """Return True when movement segment AB intersects counting segment CD."""
    o1 = _orientation(a, b, c)
    o2 = _orientation(a, b, d)
    o3 = _orientation(c, d, a)
    o4 = _orientation(c, d, b)
    return (o1 * o2 <= eps) and (o3 * o4 <= eps)


@dataclass(slots=True)
class _TrackGateState:
    stable_side: int | None = None
    stable_point: Point | None = None
    last_point: Point | None = None
    armed: bool = True
    counted_directions: set[str] = field(default_factory=set)


class LineCrossingCounter:
    """Bidirectional virtual-gate counter with dead-band and re-arming.

    A vehicle is counted only after its road-contact anchor has been observed on
    both stable sides of the finite counting segment. Frames inside the dead-band
    do not flip the side. This greatly reduces missed crossings caused by jitter
    while also preventing vehicles that merely approach the line from being
    counted.

    The same track can be counted once in each direction. That covers normal
    two-way traffic and a vehicle that genuinely crosses the gate, turns around,
    then crosses back.
    """

    def __init__(
        self,
        line: CountingLine,
        segment_margin: float = 0.08,
        dead_band_ratio: float = 0.012,
        rearm_distance_ratio: float = 0.045,
    ) -> None:
        self.line = line
        self.segment_margin = segment_margin
        self.dead_band_ratio = dead_band_ratio
        self.rearm_distance_ratio = rearm_distance_ratio
        self._tracks: dict[int, _TrackGateState] = {}
        self.in_count = 0
        self.out_count = 0

    def update(self, track_id: int, anchor: Point, frame_width: int, frame_height: int) -> str | None:
        a, b = self.line.denormalize(frame_width, frame_height)
        distance = signed_distance(anchor, a, b)
        dead_band = max(4.0, frame_height * self.dead_band_ratio)
        rearm_distance = max(dead_band * 2.0, frame_height * self.rearm_distance_ratio)
        side = 0 if abs(distance) <= dead_band else (1 if distance > 0 else -1)

        state = self._tracks.setdefault(track_id, _TrackGateState())
        previous_stable_side = state.stable_side
        previous_stable_point = state.stable_point
        state.last_point = anchor

        if side == 0:
            return None

        if previous_stable_side is None:
            state.stable_side = side
            state.stable_point = anchor
            return None

        if side == previous_stable_side:
            state.stable_point = anchor
            if not state.armed and abs(distance) >= rearm_distance:
                state.armed = True
            return None

        # The anchor has moved to the opposite stable side. Immediately after a
        # crossing we require the track to move far enough away from the gate
        # before allowing a reverse crossing. While not re-armed, ignore a quick
        # bounce back instead of flipping the stable side and creating jitter.
        if not state.armed:
            return None

        # Confirm that the movement from the last stable point actually
        # intersects the finite gate.
        if previous_stable_point is None:
            state.stable_side = side
            state.stable_point = anchor
            return None

        dx = b[0] - a[0]
        dy = b[1] - a[1]
        a_ext = (a[0] - dx * self.segment_margin, a[1] - dy * self.segment_margin)
        b_ext = (b[0] + dx * self.segment_margin, b[1] + dy * self.segment_margin)
        intersects = segments_intersect(previous_stable_point, anchor, a_ext, b_ext)

        # Update the stable state whether or not this was inside the finite gate;
        # otherwise a track moving outside the segment can later create a false
        # crossing when it re-enters the scene.
        state.stable_side = side
        state.stable_point = anchor

        if not intersects or not state.armed:
            return None

        direction = "in" if previous_stable_side < 0 < side else "out"
        if direction in state.counted_directions:
            return None

        state.counted_directions.add(direction)
        # If a frame jump already put the anchor well beyond the gate, it is safe
        # to arm immediately for a genuine reverse traversal. Otherwise the next
        # same-side observation beyond rearm_distance will arm it.
        state.armed = abs(distance) >= rearm_distance
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
