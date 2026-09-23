from __future__ import annotations

from dataclasses import dataclass

from app.counting import CountingLine


@dataclass(slots=True)
class GateROI:
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    def crop(self, frame):
        return frame[self.y1:self.y2, self.x1:self.x2]


def gate_roi_for_line(
    line: CountingLine,
    width: int,
    height: int,
    margin_ratio: float = 0.22,
    min_span_ratio: float = 0.52,
) -> GateROI:
    margin_ratio = max(0.02, min(0.48, float(margin_ratio)))
    min_span_ratio = max(0.25, min(1.0, float(min_span_ratio)))

    lx1 = min(line.x1, line.x2)
    lx2 = max(line.x1, line.x2)
    ly1 = min(line.y1, line.y2)
    ly2 = max(line.y1, line.y2)

    x1 = max(0.0, lx1 - margin_ratio)
    x2 = min(1.0, lx2 + margin_ratio)
    y1 = max(0.0, ly1 - margin_ratio)
    y2 = min(1.0, ly2 + margin_ratio)

    def expand(lo: float, hi: float) -> tuple[float, float]:
        span = hi - lo
        if span >= min_span_ratio:
            return lo, hi
        extra = (min_span_ratio - span) / 2.0
        lo = max(0.0, lo - extra)
        hi = min(1.0, hi + extra)
        if hi - lo < min_span_ratio:
            if lo <= 0.0:
                hi = min(1.0, min_span_ratio)
            else:
                lo = max(0.0, 1.0 - min_span_ratio)
        return lo, hi

    x1, x2 = expand(x1, x2)
    y1, y2 = expand(y1, y2)
    return GateROI(
        int(round(x1 * width)),
        int(round(y1 * height)),
        max(2, int(round(x2 * width))),
        max(2, int(round(y2 * height))),
    )
