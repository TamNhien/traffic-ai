"""V0.5.119 sanitized historical policy wire contract; no live environment reads."""
from __future__ import annotations

import hashlib
import json
import math
import re

POLICY_FIELDS = {'worker': (('_endpoint_precision_guard_enabled', 'bool'),
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
            ('video_origin_min_normal_ratio', 'number')),
 'resolver': (('max_gap_frames', 'int'),
              ('max_distance_ratio', 'number'),
              ('heavy_max_gap_frames', 'int'),
              ('heavy_max_distance_ratio', 'number'),
              ('raw_reuse_jump_ratio', 'number'),
              ('short_gap_alias_guard', 'bool'),
              ('two_wheel_heading_inertia', 'bool'),
              ('stationary_alias_guard', 'bool')),
 'primary': (('segment_margin', 'number'),
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
             ('origin_rescue_min_normal_ratio', 'number')),
 'anchor_span': (('enabled', 'bool'),
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
                 ('clock_reconcile_min_side_distance_ratio', 'number')),
 'heavy_center': (('history_gap_frames', 'int'),
                  ('dead_band_ratio', 'number'),
                  ('segment_margin', 'number'),
                  ('min_normal_ratio', 'number'),
                  ('min_motion_ratio', 'number'),
                  ('road_margin_ratio', 'number')),
 'two_wheel_center': (('history_gap_frames', 'int'),
                      ('interpolation_gap_frames', 'int'),
                      ('dead_band_ratio', 'number'),
                      ('segment_margin', 'number'),
                      ('segment_edge_ratio', 'number'),
                      ('min_normal_ratio', 'number'),
                      ('min_motion_ratio', 'number'),
                      ('max_jump_ratio', 'number'),
                      ('min_side_distance_ratio', 'number'),
                      ('road_margin_ratio', 'number')),
 'human_guard': (('required_strikes', 'int'),),
 'detector': (('confidence_threshold', 'number'),)}
REQUIRED_COMPONENTS = frozenset({'worker', 'resolver', 'primary', 'detector'})
DIGEST_SCOPE = 'allowlisted_effective_algorithm_parameters'
BODY_KEYS = frozenset({'schema_version', 'digest_scope', 'capture_status', 'configuration',
                       'component_presence', 'missing_fields', 'invalid_fields', 'unreadable_fields'})
REASONS = frozenset({'recorded', 'trace_missing', 'policy_not_recorded', 'capture_failed',
                     'malformed_metadata', 'metadata_limit', 'invalid_policy', 'session_mismatch',
                     'duplicate_metadata', 'service_unavailable', 'unsupported_endpoint',
                     'invalid_response', 'invalid_session'})


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def load_json(data):
    def reject_constant(_value):
        raise ValueError('nonfinite JSON scalar')
    return json.loads(data, object_pairs_hook=_unique_object, parse_constant=reject_constant)


def _scalar_valid(value, expected):
    if expected == 'bool':
        return type(value) is bool
    if expected == 'int':
        return type(value) is int
    if expected == 'number':
        if type(value) not in (int, float):
            return False
        try:
            return math.isfinite(float(value))
        except (OverflowError, ValueError):
            return False
    return expected == 'roi' and type(value) is str and value in {'full', 'road', 'gate'}


def validate_policy(policy):
    """Return only the original scoped body after complete shape/digest validation."""
    if type(policy) is not dict or set(policy) != BODY_KEYS | {'configuration_sha256'}:
        raise ValueError('policy shape')
    if type(policy['schema_version']) is not int or policy['schema_version'] != 1:
        raise ValueError('policy schema')
    if (policy['digest_scope'] != DIGEST_SCOPE or type(policy['capture_status']) is not str
            or policy['capture_status'] not in {'complete', 'partial'}):
        raise ValueError('policy scope/status')
    presence, configuration = policy['component_presence'], policy['configuration']
    if type(presence) is not dict or set(presence) != set(POLICY_FIELDS):
        raise ValueError('policy presence')
    if any(type(value) is not str or value not in {'present', 'absent'} for value in presence.values()):
        raise ValueError('policy presence value')
    present = {name for name, status in presence.items() if status == 'present'}
    if type(configuration) is not dict or set(configuration) != present:
        raise ValueError('policy configuration')
    diagnostics = []
    all_qualified = {component + '.' + name for component, fields in POLICY_FIELDS.items() for name, _ in fields}
    for key in ('missing_fields', 'invalid_fields', 'unreadable_fields'):
        values = policy[key]
        if (type(values) is not list or not all(type(v) is str for v in values)
                or values != sorted(set(values)) or not set(values) <= all_qualified):
            raise ValueError('policy diagnostic fields')
        diagnostics.extend(values)
    if len(diagnostics) != len(set(diagnostics)):
        raise ValueError('overlapping diagnostics')
    diagnostic_set = set(diagnostics)
    if any(field.split('.', 1)[0] not in present for field in diagnostics):
        raise ValueError('absent component diagnostic')
    for component in present:
        values = configuration[component]
        expected = dict(POLICY_FIELDS[component])
        if type(values) is not dict or not set(values) <= set(expected):
            raise ValueError('unknown policy field')
        if any(not _scalar_valid(value, expected[name]) for name, value in values.items()):
            raise ValueError('invalid policy scalar')
        known = {component + '.' + name for name in values}
        component_diagnostics = {field for field in diagnostic_set if field.startswith(component + '.')}
        if known & component_diagnostics or known | component_diagnostics != {component + '.' + name for name in expected}:
            raise ValueError('incomplete policy accounting')
    partial = bool(diagnostics) or any(presence[name] == 'absent' for name in REQUIRED_COMPONENTS)
    if policy['capture_status'] != ('partial' if partial else 'complete'):
        raise ValueError('inconsistent capture status')
    digest = policy['configuration_sha256']
    if type(digest) is not str or re.fullmatch(r'[0-9a-f]{64}', digest) is None:
        raise ValueError('policy digest')
    body = {key: policy[key] for key in BODY_KEYS}
    encoded = json.dumps(body, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)
    if hashlib.sha256(encoded.encode('utf-8')).hexdigest() != digest:
        raise ValueError('policy digest mismatch')
    # JSON roundtrip produces a detached tree, preserving exact numeric types.
    return json.loads(json.dumps(policy, allow_nan=False))


def validate_runtime(runtime):
    if runtime is None:
        return None
    if type(runtime) is not dict or set(runtime) != {'ai_runtime_version', 'worker_source_sha256'}:
        raise ValueError('runtime shape')
    version, digest = runtime['ai_runtime_version'], runtime['worker_source_sha256']
    if (type(version) is not str or len(version) > 64
            or re.fullmatch(r'\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?', version) is None
            or type(digest) is not str or re.fullmatch(r'[0-9a-f]{64}', digest) is None):
        raise ValueError('runtime identity')
    return {'ai_runtime_version': version, 'worker_source_sha256': digest}


def policy_result(session_id, status, reason, *, runtime=None, policy=None):
    return {'available': status == 'available', 'session_id': session_id,
            'status': status, 'reason': reason, 'metadata_verification': 'prefix_only',
            'runtime': runtime, 'policy': policy}


def validate_response(payload, session_id):
    keys = {'available', 'session_id', 'status', 'reason', 'metadata_verification', 'runtime', 'policy'}
    if type(payload) is not dict or set(payload) != keys:
        raise ValueError('response shape')
    if type(payload['session_id']) is not int or payload['session_id'] != session_id:
        raise ValueError('response session')
    status = payload['status']
    if (type(status) is not str or status not in {'available', 'not_recorded', 'invalid', 'unavailable'}
            or type(payload['available']) is not bool or payload['available'] != (status == 'available')
            or payload['metadata_verification'] != 'prefix_only'
            or type(payload['reason']) is not str or payload['reason'] not in REASONS):
        raise ValueError('response state')
    state_reasons = {
        'available': {'recorded'},
        'not_recorded': {'policy_not_recorded', 'unsupported_endpoint'},
        'unavailable': {'trace_missing', 'capture_failed', 'service_unavailable'},
        'invalid': REASONS - {'recorded', 'policy_not_recorded', 'unsupported_endpoint',
                              'trace_missing', 'capture_failed', 'service_unavailable'},
    }
    if payload['reason'] not in state_reasons[status]:
        raise ValueError('inconsistent response reason')
    runtime = validate_runtime(payload['runtime'])
    policy = validate_policy(payload['policy']) if status == 'available' else None
    if status != 'available' and payload['policy'] is not None:
        raise ValueError('unexpected unavailable policy')
    return policy_result(session_id, status, payload['reason'], runtime=runtime, policy=policy)

RESPONSE_MAX_BYTES = 128 * 1024


def fetch_recorded_policy(session_id: int, base_url: str, http_client) -> dict:
    """Optional bounded service fetch; never fall back to current environment."""
    if type(session_id) is not int or session_id <= 0:
        return policy_result(session_id, 'invalid', 'invalid_session')
    try:
        url = base_url.rstrip('/') + '/benchmark-traces/' + str(session_id) + '/policy'
        with http_client.stream('GET', url, timeout=2.0, follow_redirects=False) as response:
            if response.status_code == 404:
                return policy_result(session_id, 'not_recorded', 'unsupported_endpoint')
            if response.status_code != 200:
                return policy_result(session_id, 'unavailable', 'service_unavailable')
            announced = response.headers.get('Content-Length')
            if announced is not None and (not announced.isdigit() or int(announced) > RESPONSE_MAX_BYTES):
                return policy_result(session_id, 'invalid', 'invalid_response')
            chunks, size = [], 0
            for chunk in response.iter_bytes(chunk_size=8192):
                if type(chunk) is not bytes:
                    raise ValueError('invalid response chunk')
                size += len(chunk)
                if size > RESPONSE_MAX_BYTES:
                    return policy_result(session_id, 'invalid', 'invalid_response')
                chunks.append(chunk)
            return validate_response(load_json(b''.join(chunks)), session_id)
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError, OverflowError):
        return policy_result(session_id, 'invalid', 'invalid_response')
    except Exception:
        # HTTP exception details may include service URLs and credentials.
        return policy_result(session_id, 'unavailable', 'service_unavailable')
