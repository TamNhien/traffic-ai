from __future__ import annotations

from collections.abc import Mapping
from math import hypot

Point = tuple[float, float]


def _cross(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _point_on_segment(point: Point, a: Point, b: Point, eps: float = 1e-9) -> bool:
    if abs(_cross(a, b, point)) > eps:
        return False
    return (
        min(a[0], b[0]) - eps <= point[0] <= max(a[0], b[0]) + eps
        and min(a[1], b[1]) - eps <= point[1] <= max(a[1], b[1]) + eps
    )


def point_in_polygon(point: Point, polygon: list[Point]) -> bool:
    """Boundary-inclusive point-in-polygon test for normalized camera geometry."""
    if len(polygon) < 3:
        return False
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        a = polygon[j]
        b = polygon[i]
        if _point_on_segment(point, a, b):
            return True
        xi, yi = b
        xj, yj = a
        if (yi > y) != (yj > y):
            denom = yj - yi
            if abs(denom) > 1e-12:
                x_at_y = (xj - xi) * (y - yi) / denom + xi
                if x < x_at_y:
                    inside = not inside
        j = i
    return inside


def polygon_area(polygon: list[Point]) -> float:
    if len(polygon) < 3:
        return 0.0
    twice = 0.0
    for idx, point in enumerate(polygon):
        nxt = polygon[(idx + 1) % len(polygon)]
        twice += point[0] * nxt[1] - nxt[0] * point[1]
    return abs(twice) * 0.5


def _orientation(a: Point, b: Point, c: Point, eps: float = 1e-9) -> int:
    value = _cross(a, b, c)
    if abs(value) <= eps:
        return 0
    return 1 if value > 0 else -1


def segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    o1 = _orientation(a, b, c)
    o2 = _orientation(a, b, d)
    o3 = _orientation(c, d, a)
    o4 = _orientation(c, d, b)
    if o1 != o2 and o3 != o4:
        return True
    if o1 == 0 and _point_on_segment(c, a, b):
        return True
    if o2 == 0 and _point_on_segment(d, a, b):
        return True
    if o3 == 0 and _point_on_segment(a, c, d):
        return True
    if o4 == 0 and _point_on_segment(b, c, d):
        return True
    return False


def road_zone_from(values: Mapping[str, object]) -> list[Point]:
    return [
        (float(values["road_x1"]), float(values["road_y1"])),
        (float(values["road_x2"]), float(values["road_y2"])),
        (float(values["road_x3"]), float(values["road_y3"])),
        (float(values["road_x4"]), float(values["road_y4"])),
    ]


def validate_counting_geometry(values: Mapping[str, object], *, min_zone_area: float = 0.02, min_line_length: float = 0.05) -> str | None:
    """Return a Vietnamese validation message, or None when geometry is safe.

    V0.5.12 deliberately rejects malformed/self-crossing road polygons and new
    counting-line endpoints outside the road polygon. This keeps the editable
    yellow gate from accidentally extending onto a sidewalk after a save.
    """
    try:
        zone = road_zone_from(values)
        line_a = (float(values["line_x1"]), float(values["line_y1"]))
        line_b = (float(values["line_x2"]), float(values["line_y2"]))
    except (KeyError, TypeError, ValueError):
        return "Thiếu tọa độ vạch đếm hoặc vùng lòng đường."

    # Only opposite edges are tested; adjacent edges share a vertex by design.
    if segments_intersect(zone[0], zone[1], zone[2], zone[3]) or segments_intersect(zone[1], zone[2], zone[3], zone[0]):
        return "Vùng lòng đường đang bị bắt chéo. Hãy sắp 4 điểm xanh theo vòng quanh mặt đường, không tạo hình nơ."

    if polygon_area(zone) < min_zone_area:
        return "Vùng lòng đường quá nhỏ. Hãy kéo 4 điểm xanh bao đủ phần mặt đường cần đếm."

    if hypot(line_b[0] - line_a[0], line_b[1] - line_a[1]) < min_line_length:
        return "Vạch đếm quá ngắn. Hãy kéo hai đầu vạch vàng cách nhau xa hơn."

    if not point_in_polygon(line_a, zone) or not point_in_polygon(line_b, zone):
        return "Hai đầu vạch đếm phải nằm trong vùng Lòng đường. Không kéo vạch vàng ra lề/vỉa hè."

    return None
