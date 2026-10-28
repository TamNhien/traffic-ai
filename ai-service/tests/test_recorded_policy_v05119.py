"""Recorded policy prefix validation without FastAPI, HTTP or inference."""
import ast
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from app.policy_snapshot import POLICY_FIELDS, capture_policy_snapshot
from app.recorded_policy import (
    METADATA_MAX_LINE_BYTES, read_recorded_policy, validate_policy,
)


def snapshot():
    scalar = {'bool': False, 'int': 1, 'number': .25, 'roi': 'full'}
    return capture_policy_snapshot({name: SimpleNamespace(**{
        key: scalar[kind] for key, kind in fields}) for name, fields in POLICY_FIELDS.items()})


def signed(policy):
    body = {key: value for key, value in policy.items() if key != 'configuration_sha256'}
    policy['configuration_sha256'] = hashlib.sha256(json.dumps(
        body, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()).hexdigest()
    return policy


def rows(policy=None, session=42):
    policy = snapshot() if policy is None else policy
    return [
        {'kind': 'session_metadata', 'session_id': session, 'camera_id': 1,
         'ai_runtime_version': '0.5.118', 'worker_source_sha256': 'a' * 64},
        {'kind': 'geometry_metadata', 'session_id': session, 'camera_id': 1},
        {'kind': 'policy_metadata', 'audit_only': True, 'camera_id': 1, 'session_id': session, **policy},
        {'frame_index': 1, 'source_time_seconds': 0.0},
    ]


class RecordedPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'trace.jsonl'

    def read(self, data=None):
        if data is not None:
            self.path.write_bytes(b''.join(json.dumps(row, separators=(',', ':')).encode() + b'\n'
                                          for row in data))
        return read_recorded_policy(self.path, 42)

    def test_complete_actual_snapshot_is_returned_with_scoped_digest(self):
        result = self.read(rows())
        self.assertTrue(result['available'])
        self.assertEqual(result['status'], 'available')
        self.assertEqual(result['metadata_verification'], 'prefix_only')
        self.assertEqual(result['runtime']['ai_runtime_version'], '0.5.118')
        self.assertEqual(result['policy'], snapshot())

    def test_missing_trace_is_unknown_and_never_falls_back_to_environment(self):
        result = self.read()
        self.assertFalse(result['available'])
        self.assertEqual(result['reason'], 'trace_missing')
        self.assertIsNone(result['runtime'])
        self.assertIsNone(result['policy'])

    def test_legacy_trace_without_policy_is_not_recorded(self):
        data = rows()
        del data[2]
        result = self.read(data)
        self.assertEqual(result['status'], 'not_recorded')
        self.assertIsNone(result['policy'])

    def test_absent_optional_component_stays_distinct_from_disabled_flag(self):
        policy = snapshot()
        policy['component_presence']['anchor_span'] = 'absent'
        del policy['configuration']['anchor_span']
        result = self.read(rows(signed(policy)))
        self.assertTrue(result['available'])
        self.assertEqual(result['policy']['component_presence']['anchor_span'], 'absent')
        self.assertIs(result['policy']['configuration']['worker']['_endpoint_rescue_guard_enabled'], False)

    def test_partial_snapshot_preserves_missing_field_without_inventing_value(self):
        policy = snapshot()
        del policy['configuration']['worker']['iou']
        policy['missing_fields'] = ['worker.iou']
        policy['capture_status'] = 'partial'
        result = self.read(rows(signed(policy)))
        self.assertTrue(result['available'])
        self.assertNotIn('iou', result['policy']['configuration']['worker'])
        self.assertEqual(result['policy']['missing_fields'], ['worker.iou'])

    def test_parameter_tampering_with_unchanged_digest_is_rejected(self):
        data = rows()
        data[2]['configuration']['detector']['confidence_threshold'] = .9
        result = self.read(data)
        self.assertEqual(result['status'], 'invalid')
        self.assertIsNone(result['policy'])

    def test_unknown_fields_and_string_payloads_rejected_even_if_resigned(self):
        for component, key, value in [('worker', 'secret_token', 'private'),
                                      ('detector', 'confidence_threshold', 'private')]:
            policy = snapshot()
            policy['configuration'][component][key] = value
            result = self.read(rows(signed(policy)))
            self.assertEqual(result['status'], 'invalid')
            self.assertNotIn('private', json.dumps(result))

    def test_bool_as_numeric_wrong_types_and_nonfinite_values_rejected(self):
        for value in [True, '0.2', None, float('nan'), float('inf')]:
            data = rows()
            data[2]['configuration']['detector']['confidence_threshold'] = value
            self.assertEqual(self.read(data)['status'], 'invalid')

    def test_duplicate_policy_or_header_is_not_silently_selected(self):
        for index in (0, 2):
            data = rows()
            data.insert(3, copy.deepcopy(data[index]))
            self.assertEqual(self.read(data)['reason'], 'duplicate_metadata')

    def test_policy_requires_header_then_geometry_and_matching_session(self):
        data = rows()
        data[1], data[2] = data[2], data[1]
        self.assertEqual(self.read(data)['status'], 'invalid')
        data = rows()
        data[2]['session_id'] = 43
        self.assertEqual(self.read(data)['reason'], 'session_mismatch')

    def test_unsupported_schema_and_fake_policy_observation_are_rejected(self):
        data = rows()
        data[2]['schema_version'] = 2
        self.assertEqual(self.read(data)['status'], 'invalid')
        data = rows()
        data[2]['source_time_seconds'] = 0
        self.assertEqual(self.read(data)['status'], 'invalid')

    def test_duplicate_json_keys_and_malformed_utf8_are_rejected(self):
        for content in [b'{"kind":"session_metadata","kind":"policy_metadata"}\n', b'\xff\n']:
            self.path.write_bytes(content)
            self.assertEqual(self.read()['status'], 'invalid')

    def test_metadata_line_limit_and_truncated_record_fail_cleanly(self):
        for content in [b'x' * (METADATA_MAX_LINE_BYTES + 100), b'{"kind":']:
            self.path.write_bytes(content)
            self.assertEqual(self.read()['reason'], 'metadata_limit')

    def test_reader_stops_before_large_first_frame_without_reading_tail(self):
        data = rows()[:3]
        self.read(data)
        with self.path.open('ab') as stream:
            stream.write(b'{"frame_index":1,"gate_tracks":[' + b'x' * 2_000_000)
        result = self.read()
        self.assertTrue(result['available'])
        self.assertEqual(result['metadata_verification'], 'prefix_only')

    def test_capture_failure_has_sanitized_unavailable_marker(self):
        data = rows()
        data[2] = {'kind': 'policy_metadata', 'session_id': 42, 'camera_id': 1,
                   'audit_only': True, 'schema_version': 1,
                   'digest_scope': 'allowlisted_effective_algorithm_parameters',
                   'capture_status': 'unavailable', 'reason': 'capture_failed'}
        result = self.read(data)
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(result['reason'], 'capture_failed')
        self.assertIsNone(result['policy'])

    def test_complete_flag_requires_all_fields_and_digest_validation_is_read_only(self):
        policy = snapshot()
        before = copy.deepcopy(policy)
        self.assertEqual(validate_policy(policy), before)
        self.assertEqual(policy, before)
        del policy['configuration']['worker']['iou']
        with self.assertRaises(ValueError):
            validate_policy(signed(policy))

    def test_actual_ai_route_reads_requested_session_and_disables_caching(self):
        path = Path(__file__).parents[1] / 'app/main.py'
        tree = ast.parse(path.read_text())
        node = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == 'benchmark_trace_policy')
        node.decorator_list = []
        for arg in node.args.args:
            arg.annotation = None
        node.returns = None
        calls = []
        namespace = {'trace_path': lambda session: ('trace', session),
                     'read_recorded_policy': lambda path, session: calls.append((path, session)) or {'available': False}}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(path), 'exec'), namespace)
        response = SimpleNamespace(headers={})
        self.assertEqual(namespace['benchmark_trace_policy'](42, response), {'available': False})
        self.assertEqual(calls, [(('trace', 42), 42)])
        self.assertEqual(response.headers['Cache-Control'], 'no-store')


if __name__ == '__main__':
    unittest.main()
