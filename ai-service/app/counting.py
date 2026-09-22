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


class LineCrossingCounter:
    def __init__(self, line: CountingLine, segment_margin: float = 0.05) -> None:
        self.line = line
        self.segment_margin = segment_margin
        self._previous_side: dict[int, float] = {}
        self._counted_tracks: set[int] = set()

    def update(self, track_id: int, center: Point, frame_width: int, frame_height: int) -> str | None:
        a, b = self.line.denormalize(frame_width, frame_height)
        current = signed_side(center, a, b)
        if abs(current) <= 1e-6:
            return None

        previous = self._previous_side.get(track_id)
        self._previous_side[track_id] = current
        if previous is None or track_id in self._counted_tracks:
            return None
        if (previous < 0) == (current < 0):
            return None

        t = projection_parameter(center, a, b)
        if t < -self.segment_margin or t > 1.0 + self.segment_margin:
            return None

        self._counted_tracks.add(track_id)
        return "in" if previous < 0 <= current else "out"

    @property
    def counted_tracks(self) -> int:
        return len(self._counted_tracks)
