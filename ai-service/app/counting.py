from __future__ import annotations

from dataclasses import dataclass

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
    """Return True when movement segment AB intersects counting segment CD.

    Using the movement segment is more robust than checking only the current
    anchor position. A fast vehicle can move from one side of the line to the
    other between two frames and must still be counted.
    """
    o1 = _orientation(a, b, c)
    o2 = _orientation(a, b, d)
    o3 = _orientation(c, d, a)
    o4 = _orientation(c, d, b)
    return (o1 * o2 <= eps) and (o3 * o4 <= eps)


class LineCrossingCounter:
    def __init__(self, line: CountingLine, segment_margin: float = 0.06) -> None:
        self.line = line
        self.segment_margin = segment_margin
        self._previous_point: dict[int, Point] = {}
        self._previous_side: dict[int, float] = {}
        self._counted_tracks: set[int] = set()
        self.in_count = 0
        self.out_count = 0

    def update(self, track_id: int, anchor: Point, frame_width: int, frame_height: int) -> str | None:
        a, b = self.line.denormalize(frame_width, frame_height)
        current_side = signed_side(anchor, a, b)
        previous_point = self._previous_point.get(track_id)
        previous_side = self._previous_side.get(track_id)

        # Do not erase the last non-zero side when the anchor lands exactly on
        # the line. This preserves a crossing sequence such as above -> line -> below.
        if abs(current_side) <= 1e-6:
            self._previous_point[track_id] = anchor
            return None

        self._previous_point[track_id] = anchor
        self._previous_side[track_id] = current_side

        if previous_point is None or previous_side is None or track_id in self._counted_tracks:
            return None

        # Require an actual side change.
        if (previous_side < 0) == (current_side < 0):
            return None

        # Extend the gate a small amount at both ends, then validate that the
        # tracked movement segment really crosses the gate.
        dx = b[0] - a[0]
        dy = b[1] - a[1]
        a_ext = (a[0] - dx * self.segment_margin, a[1] - dy * self.segment_margin)
        b_ext = (b[0] + dx * self.segment_margin, b[1] + dy * self.segment_margin)
        if not segments_intersect(previous_point, anchor, a_ext, b_ext):
            return None

        direction = "in" if previous_side < 0 < current_side else "out"
        self._counted_tracks.add(track_id)
        if direction == "in":
            self.in_count += 1
        else:
            self.out_count += 1
        return direction

    @property
    def counted_tracks(self) -> int:
        return len(self._counted_tracks)
