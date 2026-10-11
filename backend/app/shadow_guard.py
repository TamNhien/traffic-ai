"""Ground-truth-independent ultra-local gate crossing ID-switch guard.

Small, pure rules used by backend persistence and offline counterfactual tests.
This module MUST NOT read benchmark labels, ground truth or session IDs.
"""
from __future__ import annotations

DIRECT_SHADOW_MAX_TIME_SECONDS = 0.32
DIRECT_SHADOW_MAX_DISTANCE = 0.009
LEGACY_DIRECT_SHADOW_MAX_TIME_SECONDS = 0.42
LEGACY_DIRECT_SHADOW_MAX_DISTANCE = 0.006


def direct_ultra_spatial_shadow_duplicate(
    time_delta: float,
    distance: float,
    current_method: str | None,
    other_method: str | None,
) -> bool:
    """Only collapse two DIRECT crossing events at nearly identical gate points.

    The caller must separately check: same session, same direction, exact class,
    distinct tracking IDs, finite normalized coordinates and source time.
    Tight thresholds avoid suppressing dense legitimate traffic.
    """
    return (
        {str(current_method or ''), str(other_method or '')} == {'direct'}
        and 0.0 <= float(time_delta)
        and 0.0 <= float(distance)
        and (
            (float(time_delta) <= LEGACY_DIRECT_SHADOW_MAX_TIME_SECONDS
             and float(distance) <= LEGACY_DIRECT_SHADOW_MAX_DISTANCE)
            or (float(time_delta) <= DIRECT_SHADOW_MAX_TIME_SECONDS
                and float(distance) <= DIRECT_SHADOW_MAX_DISTANCE)
        )
    )
