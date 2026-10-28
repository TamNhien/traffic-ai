"""Bounded finite-endpoint precision policy (rescued extension: V0.5.118).

A crossing directly at the finite line start endpoint can be lower-quality evidence than one well
inside the finite gate. For video two-wheel interpolations, require a stable
center-side confirmation near the start endpoint. The worker can explicitly
enable the same check for rescued crossings. Direct crossings, four-wheel
vehicles and missing geometry remain unaffected; the worker limits use to video.

Caution: this is a policy hypothesis. Benchmark labels are never read by the
worker. Validate using an A/B video replay; the trace audit is counterfactual.
"""
from __future__ import annotations

from math import isfinite


def endpoint_precision_rejection(
    line: tuple[tuple[float, float], tuple[float, float]],
    crossing_xy: tuple[float, float] | None,
    center_signed: float | None,
    direction: str,
    label: str,
    method: str | None,
    *,
    allow_rescued: bool = False,
    edge_fraction: float = 0.08,
    stable_center_side: float = 0.04,
) -> dict | None:
    if method != 'interpolated' and not (allow_rescued and method == 'rescued'):
        return None
    if label not in {'motorcycle', 'bicycle'} or direction not in {'in', 'out'}:
        return None
    if crossing_xy is None or center_signed is None:
        return None
    try:
        (ax, ay), (bx, by) = line
        x, y = crossing_xy
        values = (ax, ay, bx, by, x, y, center_signed, edge_fraction, stable_center_side)
        if not all(isfinite(float(v)) for v in values):
            return None
        if not 0 <= x <= 1 or not 0 <= y <= 1:
            return None
        norm2 = (bx-ax)**2+(by-ay)**2
        if norm2 < 1e-8 or not (0.0 < edge_fraction <= 0.15) or not (0.0 < stable_center_side <= 0.08):
            return None
        projection = ((x-ax)*(bx-ax)+(y-ay)*(by-ay))/norm2
        if projection < 0 or projection > 1:
            return None
        if projection >= edge_fraction:
            return None
        # The body center must remain close to the line, rather than have
        # clearly advanced onto the destination side already. This avoids
        # rejecting a stable genuine passage just because its anchor is near
        # the endpoint. signed convention: positive below line (IN side).
        destination_signed = float(center_signed) if direction == 'in' else -float(center_signed)
        if destination_signed >= stable_center_side:
            return None
        return {
            'kind': ('finite_endpoint_rescue_center_uncertain'
                     if method == 'rescued' else 'finite_endpoint_center_uncertain'),
            'projection': round(projection, 6),
            'center_signed': round(float(center_signed), 6),
            'direction': direction, 'method': method,
            'edge_fraction': edge_fraction,
            'stable_center_side': stable_center_side,
        }
    except (TypeError, ValueError):
        return None
