"""V0.5.109: read-only strict-vs-tolerant road eligibility diagnostic.

The existing ROAD telemetry uses strict polygon containment, whereas the
counter permits a bounded anchor margin. This helper does NOT admit a count:
a single visible anchor cannot establish an actual crossing or identity.
"""
from __future__ import annotations

from math import isfinite

from app.counting import point_segment_distance


def road_gate_probe(anchor, line, road_zone, width, height, *, margin_ratio=0.0,
                    near_gate_radius=0.035):
    try:
        width, height = int(width), int(height)
        x, y = float(anchor[0]), float(anchor[1])
        margin_ratio, near_gate_radius = float(margin_ratio), float(near_gate_radius)
        if (width < 2 or height < 2 or not all(map(isfinite, (x, y, margin_ratio, near_gate_radius)))
                or not 0 <= margin_ratio <= .2 or not 0 < near_gate_radius <= .2):
            return None
        strict = road_zone is None or bool(road_zone.contains((x, y), width, height))
        eligible = road_zone is None or bool(road_zone.contains_with_margin(
            (x, y), width, height, margin_ratio))
        a, b = line.denormalize(width, height)
        gate_distance = point_segment_distance((x, y), a, b) / min(width, height)
        if not isfinite(gate_distance):
            return None
        return {
            'strict_road': strict,
            'margin_eligible': eligible,
            'margin_only': bool(eligible and not strict),
            'near_finite_gate': bool(gate_distance <= near_gate_radius),
            'near_eligible_gate': bool(eligible and gate_distance <= near_gate_radius),
            'finite_gate_distance': round(gate_distance, 6),
        }
    except (TypeError, ValueError, OverflowError, AttributeError):
        return None
