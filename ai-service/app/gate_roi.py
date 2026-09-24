from __future__ import annotations

from dataclasses import dataclass
from math import hypot

from app.counting import CountingLine, RoadZone


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
    margin_ratio: float = 0.16,
    min_span_ratio: float = 0.52,
    endpoint_margin_ratio: float = 0.035,
) -> GateROI:
    """Build a compact ROI around the finite counting segment.

    Older releases expanded both image axes to at least 52% of the frame, which
    made a horizontal gate unnecessarily tall and slowed inference. V0.5.8 pads
    primarily *normal* to the line for tracking context and only a small amount
    beyond the two endpoints. This keeps enough before/after-line history while
    excluding most sidewalk/off-gate traffic from detector work.
    """

    margin_ratio = max(0.03, min(0.40, float(margin_ratio)))
    min_span_ratio = max(0.20, min(1.0, float(min_span_ratio)))
    endpoint_margin_ratio = max(0.0, min(0.15, float(endpoint_margin_ratio)))

    a, b = line.denormalize(width, height)
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    length = max(hypot(dx, dy), 1.0)
    tx, ty = dx / length, dy / length
    nx, ny = -ty, tx

    base_scale = max(1.0, min(width, height))
    normal_pad = base_scale * margin_ratio
    endpoint_pad = base_scale * endpoint_margin_ratio

    a_pad = (a[0] - tx * endpoint_pad, a[1] - ty * endpoint_pad)
    b_pad = (b[0] + tx * endpoint_pad, b[1] + ty * endpoint_pad)
    corners = [
        (a_pad[0] + nx * normal_pad, a_pad[1] + ny * normal_pad),
        (a_pad[0] - nx * normal_pad, a_pad[1] - ny * normal_pad),
        (b_pad[0] + nx * normal_pad, b_pad[1] + ny * normal_pad),
        (b_pad[0] - nx * normal_pad, b_pad[1] - ny * normal_pad),
    ]

    x1 = max(0.0, min(p[0] for p in corners))
    x2 = min(float(width), max(p[0] for p in corners))
    y1 = max(0.0, min(p[1] for p in corners))
    y2 = min(float(height), max(p[1] for p in corners))

    # Keep a useful tangent span if the user drew a very short gate. Apply this
    # only on the dominant line axis so the normal axis remains compact.
    if abs(dx) >= abs(dy):
        required = width * min_span_ratio
        current = x2 - x1
        if current < required:
            extra = (required - current) / 2.0
            x1 = max(0.0, x1 - extra)
            x2 = min(float(width), x2 + extra)
            if x2 - x1 < required:
                if x1 <= 0.0:
                    x2 = min(float(width), required)
                else:
                    x1 = max(0.0, float(width) - required)
    else:
        required = height * min_span_ratio
        current = y2 - y1
        if current < required:
            extra = (required - current) / 2.0
            y1 = max(0.0, y1 - extra)
            y2 = min(float(height), y2 + extra)
            if y2 - y1 < required:
                if y1 <= 0.0:
                    y2 = min(float(height), required)
                else:
                    y1 = max(0.0, float(height) - required)

    ix1 = max(0, min(width - 2, int(round(x1))))
    iy1 = max(0, min(height - 2, int(round(y1))))
    ix2 = max(ix1 + 2, min(width, int(round(x2))))
    iy2 = max(iy1 + 2, min(height, int(round(y2))))
    return GateROI(ix1, iy1, ix2, iy2)


def road_zone_roi(
    road_zone: RoadZone,
    width: int,
    height: int,
    margin_ratio: float = 0.02,
) -> GateROI:
    """Return a tight rectangular inference ROI around the drivable polygon.

    V0.5.13 tracks vehicles across the roadway instead of waiting until they
    enter the narrow counting-line strip.  This gives ByteTrack several frames
    of history before/after the gate while still excluding most sidewalk area.
    """
    margin_ratio = max(0.0, min(0.20, float(margin_ratio)))
    points = road_zone.denormalize(width, height)
    pad = max(2.0, min(width, height) * margin_ratio)
    x1 = max(0.0, min(x for x, _ in points) - pad)
    y1 = max(0.0, min(y for _, y in points) - pad)
    x2 = min(float(width), max(x for x, _ in points) + pad)
    y2 = min(float(height), max(y for _, y in points) + pad)

    ix1 = max(0, min(width - 2, int(round(x1))))
    iy1 = max(0, min(height - 2, int(round(y1))))
    ix2 = max(ix1 + 2, min(width, int(round(x2))))
    iy2 = max(iy1 + 2, min(height, int(round(y2))))
    return GateROI(ix1, iy1, ix2, iy2)
