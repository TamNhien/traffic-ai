"""V0.5.119 bounded prefix reader for effective historical policy metadata.

This validates only the metadata prefix; it does not certify trace closure or
all later frame bytes. Counting and scoring are never changed by this reader.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

from app.policy_snapshot import POLICY_FIELDS

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

PREFIX_MAX_BYTES = 256 * 1024
METADATA_MAX_LINE_BYTES = 64 * 1024
PREFIX_MAX_LINES = 8


def read_recorded_policy(path: Path, session_id: int) -> dict:
    if type(session_id) is not int or session_id <= 0:
        return policy_result(session_id, 'invalid', 'invalid_session')
    runtime = None
    try:
        with path.open('rb') as stream:
            used = 0
            header = geometry = policy = None
            for _ in range(PREFIX_MAX_LINES):
                line = stream.readline(min(METADATA_MAX_LINE_BYTES + 1, PREFIX_MAX_BYTES - used + 1))
                used += len(line)
                if not line:
                    break
                if used > PREFIX_MAX_BYTES:
                    return policy_result(session_id, 'invalid', 'metadata_limit')
                # A frame can exceed the metadata line cap. We inspect only its
                # prefix and stop before parsing any frame payload or later data.
                if re.match(rb'\s*\{\s*"frame_index"\s*:', line):
                    break
                if len(line) > METADATA_MAX_LINE_BYTES or not line.endswith(b'\n'):
                    return policy_result(session_id, 'invalid', 'metadata_limit')
                row = load_json(line)
                if type(row) is not dict:
                    raise ValueError('metadata row')
                kind = row.get('kind')
                if kind not in {'session_metadata', 'geometry_metadata', 'policy_metadata'}:
                    # A legacy observation may order its keys differently.
                    if 'frame_index' in row:
                            break
                    raise ValueError('unexpected prefix row')
                if type(row.get('session_id')) is not int or row['session_id'] != session_id:
                    return policy_result(session_id, 'invalid', 'session_mismatch')
                if kind == 'session_metadata':
                    if header is not None or geometry is not None or policy is not None:
                        return policy_result(session_id, 'invalid', 'duplicate_metadata')
                    header = row
                    if 'ai_runtime_version' in row or 'worker_source_sha256' in row:
                        runtime = validate_runtime({key: row.get(key) for key in ('ai_runtime_version', 'worker_source_sha256')})
                elif kind == 'geometry_metadata':
                    if header is None or geometry is not None or policy is not None:
                        return policy_result(session_id, 'invalid', 'duplicate_metadata')
                    geometry = row
                else:
                    if header is None or geometry is None or policy is not None:
                        return policy_result(session_id, 'invalid', 'duplicate_metadata')
                    if 'frame_index' in row or 'source_time_seconds' in row:
                        raise ValueError('synthetic policy observation')
                    if row.get('capture_status') == 'unavailable':
                        unavailable_keys = {'kind', 'audit_only', 'camera_id', 'session_id',
                                            'schema_version', 'digest_scope', 'capture_status', 'reason'}
                        if (set(row) != unavailable_keys or row.get('reason') != 'capture_failed'
                                or row.get('audit_only') is not True or type(row.get('camera_id')) is not int
                                or type(row.get('schema_version')) is not int or row['schema_version'] != 1
                                or row.get('digest_scope') != DIGEST_SCOPE):
                            raise ValueError('unavailable policy wrapper')
                        policy = 'unavailable'
                    else:
                        allowed = BODY_KEYS | {'configuration_sha256', 'kind', 'audit_only', 'camera_id', 'session_id'}
                        if set(row) != allowed or row.get('audit_only') is not True or type(row.get('camera_id')) is not int:
                            raise ValueError('policy metadata wrapper')
                        policy = validate_policy({key: row[key] for key in BODY_KEYS | {'configuration_sha256'}})
            else:
                return policy_result(session_id, 'invalid', 'metadata_limit')
            if header is None:
                return policy_result(session_id, 'invalid', 'malformed_metadata')
            if policy is None:
                return policy_result(session_id, 'not_recorded', 'policy_not_recorded', runtime=runtime)
            if policy == 'unavailable':
                return policy_result(session_id, 'unavailable', 'capture_failed', runtime=runtime)
            return policy_result(session_id, 'available', 'recorded', runtime=runtime, policy=policy)
    except FileNotFoundError:
        return policy_result(session_id, 'unavailable', 'trace_missing')
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        return policy_result(session_id, 'invalid', 'malformed_metadata')
