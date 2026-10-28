"""Sanitized snapshots of effective algorithm parameters for benchmark traces.

This is an explicit scalar allowlist, not a complete run identity. Model assets,
geometry, source media and source clocks are recorded separately. Capture reads
constructed objects, so clamped values are recorded instead of environment text.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping

SCHEMA_VERSION = 1
DIGEST_SCOPE = "allowlisted_effective_algorithm_parameters"

# Field names are reviewed literals. Never enumerate an object's attributes or
# read environment variables here: both may expose credentials and paths.
POLICY_FIELDS: dict[str, tuple[tuple[str, str], ...]] = {
    'worker': (
        ('_endpoint_precision_guard_enabled', 'bool'),
        ('_endpoint_rescue_guard_enabled', 'bool'),
        ('_raw_handoff_guard_enabled', 'bool'),
        ('_stationary_alias_guard_enabled', 'bool'),
        ('_two_wheel_fragment_guard_enabled', 'bool'),
        ('hybrid_recall', 'bool'),
        ('hybrid_mode', 'bool'),
        ('imgsz', 'int'),
        ('process_max_width', 'int'),
        ('gate_roi_enabled', 'bool'),
        ('detection_roi_mode', 'roi'),
        ('road_roi_margin', 'number'),
        ('gate_roi_margin', 'number'),
        ('gate_roi_min_span', 'number'),
        ('gate_endpoint_margin', 'number'),
        ('refine_at_crossing', 'bool'),
        ('dual_class_refine', 'bool'),
        ('refine_imgsz', 'int'),
        ('refine_max_per_frame', 'int'),
        ('refine_max_lag', 'number'),
        ('refine_background_warmup', 'bool'),
        ('class_refine_interval', 'int'),
        ('class_refine_heavy_interval', 'int'),
        ('class_refine_gate_distance_ratio', 'number'),
        ('class_override_ttl_frames', 'int'),
        ('bicycle_override_ttl_frames', 'int'),
        ('heavy_override_ttl_frames', 'int'),
        ('refine_target_min_iou', 'number'),
        ('refine_target_min_coverage', 'number'),
        ('refine_consensus_min_hits', 'int'),
        ('refine_consensus_history_frames', 'int'),
        ('bicycle_consensus_conf', 'number'),
        ('bicycle_consensus_min_hits', 'int'),
        ('bicycle_consensus_margin', 'number'),
        ('bicycle_consensus_min_strong', 'number'),
        ('bicycle_consensus_min_sources', 'int'),
        ('bicycle_consensus_single_source_strong', 'number'),
        ('bicycle_context_rescue_enabled', 'bool'),
        ('_bicycle_repeated_target_context_enabled', 'bool'),
        ('bicycle_context_pad_x', 'number'),
        ('bicycle_context_pad_y', 'number'),
        ('bicycle_context_dual_conf', 'number'),
        ('bicycle_context_single_conf', 'number'),
        ('bicycle_context_min_source_conf', 'number'),
        ('bicycle_context_min_strong', 'number'),
        ('bicycle_context_max_per_frame', 'int'),
        ('bicycle_context_temporal_min_hits', 'int'),
        ('bicycle_context_temporal_conf', 'number'),
        ('bicycle_context_temporal_strong', 'number'),
        ('bicycle_context_temporal_combined', 'number'),
        ('bicycle_context_weak_motor_max_conf', 'number'),
        ('bicycle_context_weak_motor_dual_conf', 'number'),
        ('bicycle_context_weak_motor_min_strong', 'number'),
        ('bicycle_context_competitive_max_motor_conf', 'number'),
        ('bicycle_context_competitive_min_source_conf', 'number'),
        ('bicycle_context_competitive_source_margin', 'number'),
        ('bicycle_context_competitive_dual_conf', 'number'),
        ('bicycle_context_competitive_fused_margin', 'number'),
        ('bicycle_context_competitive_single_conf', 'number'),
        ('bicycle_context_near_margin_max_motor_conf', 'number'),
        ('bicycle_context_near_margin_min_source_conf', 'number'),
        ('bicycle_context_near_margin_source_win', 'number'),
        ('bicycle_context_near_margin_motor_veto', 'number'),
        ('bicycle_context_near_margin_dual_conf', 'number'),
        ('bicycle_context_near_margin_fused_margin', 'number'),
        ('bicycle_context_xframe_enabled', 'bool'),
        ('bicycle_context_xframe_history', 'int'),
        ('bicycle_context_xframe_gate_distance_ratio', 'number'),
        ('bicycle_context_xframe_interval', 'int'),
        ('bicycle_context_xframe_max_per_frame', 'int'),
        ('bicycle_context_xframe_max_motor_conf', 'number'),
        ('bicycle_context_xframe_min_source_conf', 'number'),
        ('bicycle_context_xframe_min_frames', 'int'),
        ('bicycle_context_xframe_min_sources', 'int'),
        ('bicycle_context_xframe_source_win', 'number'),
        ('bicycle_context_xframe_motor_veto', 'number'),
        ('bicycle_context_xframe_min_strong', 'number'),
        ('bicycle_context_xframe_dual_conf', 'number'),
        ('bicycle_context_xframe_fused_margin', 'number'),
        ('truck_consensus_conf', 'number'),
        ('human_guard_enabled', 'bool'),
        ('human_guard_imgsz', 'int'),
        ('human_guard_check_interval', 'int'),
        ('human_guard_conf', 'number'),
        ('human_guard_pending_max_frames', 'int'),
        ('video_deterministic', 'bool'),
        ('video_deterministic_seed', 'int'),
        ('cross_time_max_interp_seconds', 'number'),
        ('cross_time_max_rescue_seconds', 'number'),
        ('cross_time_anchor_span_seconds', 'number'),
        ('truck_lock_car_demotion_conf', 'number'),
        ('truck_lock_car_demotion_frames', 'int'),
        ('iou', 'number'),
        ('agnostic_nms', 'bool'),
        ('heavy_duplicate_iou', 'number'),
        ('heavy_anchor_inset_ratio', 'number'),
        ('heavy_center_rescue_enabled', 'bool'),
        ('heavy_center_history_gap', 'int'),
        ('heavy_center_min_normal_ratio', 'number'),
        ('heavy_center_road_margin_ratio', 'number'),
        ('two_wheel_center_rescue_enabled', 'bool'),
        ('two_wheel_center_history_gap', 'int'),
        ('two_wheel_center_min_normal_ratio', 'number'),
        ('two_wheel_center_max_jump_ratio', 'number'),
        ('two_wheel_center_min_side_ratio', 'number'),
        ('two_wheel_center_road_margin_ratio', 'number'),
        ('two_wheel_center_segment_edge_ratio', 'number'),
        ('two_wheel_center_min_track_hits', 'int'),
        ('video_origin_rescue_frames', 'int'),
        ('video_origin_distance_ratio', 'number'),
        ('video_origin_min_normal_ratio', 'number'),
    ),
    'resolver': (
        ('max_gap_frames', 'int'),
        ('max_distance_ratio', 'number'),
        ('heavy_max_gap_frames', 'int'),
        ('heavy_max_distance_ratio', 'number'),
        ('raw_reuse_jump_ratio', 'number'),
        ('short_gap_alias_guard', 'bool'),
        ('two_wheel_heading_inertia', 'bool'),
        ('stationary_alias_guard', 'bool'),
    ),
    'primary': (
        ('segment_margin', 'number'),
        ('dead_band_ratio', 'number'),
        ('rearm_distance_ratio', 'number'),
        ('history_gap_frames', 'int'),
        ('interpolation_gap_frames', 'int'),
        ('min_perpendicular_ratio', 'number'),
        ('min_crossing_motion_ratio', 'number'),
        ('startup_grace_frames', 'int'),
        ('side_confirm_samples', 'int'),
        ('crossing_cooldown_frames', 'int'),
        ('passage_rearm_min_frames', 'int'),
        ('road_anchor_margin_ratio', 'number'),
        ('fast_confirm_distance_ratio', 'number'),
        ('adaptive_cooldown', 'bool'),
        ('cooldown_release_ratio', 'number'),
        ('rescue_min_normal_ratio', 'number'),
        ('rescue_max_jump_ratio', 'number'),
        ('rescue_min_side_distance_ratio', 'number'),
        ('rescue_strict_gap_frames', 'int'),
        ('rescue_strict_min_normal_ratio', 'number'),
        ('rescue_strict_max_jump_ratio', 'number'),
        ('rescue_strict_min_side_distance_ratio', 'number'),
        ('lineage_rescue_guard', 'bool'),
        ('lineage_rescue_min_normal_ratio', 'number'),
        ('lineage_rescue_max_jump_ratio', 'number'),
        ('lineage_rescue_min_side_distance_ratio', 'number'),
        ('lineage_rescue_confirm_samples', 'int'),
        ('bracket_confirm', 'bool'),
        ('bracket_confirm_min_normal_ratio', 'number'),
        ('bracket_confirm_max_gap_frames', 'int'),
        ('late_geometry_confirm', 'bool'),
        ('late_geometry_confirm_min_normal_ratio', 'number'),
        ('late_geometry_confirm_max_jump_ratio', 'number'),
        ('late_geometry_confirm_min_side_distance_ratio', 'number'),
        ('late_geometry_confirm_max_gap_frames', 'int'),
        ('origin_rescue_frames', 'int'),
        ('origin_rescue_distance_ratio', 'number'),
        ('origin_rescue_min_normal_ratio', 'number'),
    ),
    'anchor_span': (
        ('enabled', 'bool'),
        ('history_gap_frames', 'int'),
        ('dead_band_ratio', 'number'),
        ('segment_margin', 'number'),
        ('min_normal_ratio', 'number'),
        ('immediate_min_normal_ratio', 'number'),
        ('max_jump_ratio', 'number'),
        ('min_side_distance_ratio', 'number'),
        ('immediate_min_side_distance_ratio', 'number'),
        ('road_margin_ratio', 'number'),
        ('road_corridor_margin_ratio', 'number'),
        ('post_confirm_samples', 'int'),
        ('post_confirm_max_gap_frames', 'int'),
        ('post_confirm_opposite_samples', 'int'),
        ('same_direction_min_frames', 'int'),
        ('lost_finalize_min_normal_ratio', 'number'),
        ('lost_finalize_min_side_distance_ratio', 'number'),
        ('clock_reconcile_max_gap_frames', 'int'),
        ('clock_reconcile_min_normal_ratio', 'number'),
        ('clock_reconcile_min_side_distance_ratio', 'number'),
    ),
    'heavy_center': (
        ('history_gap_frames', 'int'),
        ('dead_band_ratio', 'number'),
        ('segment_margin', 'number'),
        ('min_normal_ratio', 'number'),
        ('min_motion_ratio', 'number'),
        ('road_margin_ratio', 'number'),
    ),
    'two_wheel_center': (
        ('history_gap_frames', 'int'),
        ('interpolation_gap_frames', 'int'),
        ('dead_band_ratio', 'number'),
        ('segment_margin', 'number'),
        ('segment_edge_ratio', 'number'),
        ('min_normal_ratio', 'number'),
        ('min_motion_ratio', 'number'),
        ('max_jump_ratio', 'number'),
        ('min_side_distance_ratio', 'number'),
        ('road_margin_ratio', 'number'),
    ),
    'human_guard': (
        ('required_strikes', 'int'),
    ),
    'detector': (
        ('confidence_threshold', 'number'),
    ),
}
REQUIRED_COMPONENTS = frozenset({"worker", "resolver", "primary", "detector"})


def _validated_scalar(value: object, expected: str) -> tuple[bool, object]:
    if expected == "bool":
        return type(value) is bool, value
    if expected == "int":
        return type(value) is int, value
    if expected == "number":
        if type(value) not in (int, float):
            return False, None
        try:
            converted = float(value)
        except (OverflowError, ValueError):
            return False, None
        return math.isfinite(converted), converted
    if expected == "roi":
        return type(value) is str and value in {"full", "road", "gate"}, value
    return False, None


def capture_policy_snapshot(components: Mapping[str, object | None]) -> dict:
    """Read known scalar attributes only; errors expose field names, never text.

    Optional absent components are explicit, and do not fabricate disabled
    values. A missing required component or unavailable field marks a partial
    capture. The digest covers this scoped, sanitized snapshot only.
    """
    if not isinstance(components, Mapping):
        raise TypeError("policy components must be a mapping")
    configuration: dict[str, dict] = {}
    presence: dict[str, str] = {}
    missing: list[str] = []
    invalid: list[str] = []
    unreadable: list[str] = []
    required_absent = False
    for component_name, fields in POLICY_FIELDS.items():
        component = components.get(component_name)
        presence[component_name] = "present" if component is not None else "absent"
        if component is None:
            required_absent = required_absent or component_name in REQUIRED_COMPONENTS
            continue
        values: dict[str, object] = {}
        for field_name, expected in fields:
            qualified = f"{component_name}.{field_name}"
            try:
                value = getattr(component, field_name)
            except AttributeError:
                missing.append(qualified)
                continue
            except Exception:
                unreadable.append(qualified)
                continue
            valid, sanitized = _validated_scalar(value, expected)
            if not valid:
                invalid.append(qualified)
                continue
            values[field_name] = sanitized
        configuration[component_name] = values
    body = {
        "schema_version": SCHEMA_VERSION,
        "digest_scope": DIGEST_SCOPE,
        "capture_status": "partial" if required_absent or missing or invalid or unreadable else "complete",
        "configuration": configuration,
        "component_presence": presence,
        "missing_fields": sorted(missing),
        "invalid_fields": sorted(invalid),
        "unreadable_fields": sorted(unreadable),
    }
    serialized = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return {**body, "configuration_sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest()}

