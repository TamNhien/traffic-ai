"""Pure policy transport tests and production-route AST seam; no HTTP/ORM run."""
import ast
from contextlib import contextmanager
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from app.recorded_policy import (
    POLICY_FIELDS, RESPONSE_MAX_BYTES, fetch_recorded_policy, policy_result, validate_policy,
)


def snapshot():
    scalar = {'bool': False, 'int': 1, 'number': .25, 'roi': 'full'}
    policy = {
        'schema_version': 1, 'digest_scope': 'allowlisted_effective_algorithm_parameters',
        'capture_status': 'complete',
        'configuration': {component: {name: scalar[kind] for name, kind in fields}
                          for component, fields in POLICY_FIELDS.items()},
        'component_presence': {component: 'present' for component in POLICY_FIELDS},
        'missing_fields': [], 'invalid_fields': [], 'unreadable_fields': [],
    }
    encoded = json.dumps(policy, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)
    return {**policy, 'configuration_sha256': hashlib.sha256(encoded.encode()).hexdigest()}


def payload():
    return policy_result(42, 'available', 'recorded', runtime={
        'ai_runtime_version': '0.5.118', 'worker_source_sha256': 'a' * 64}, policy=snapshot())


class Client:
    def __init__(self, body=None, status=200, headers=None, error=None):
        self.body = json.dumps(payload()).encode() if body is None else body
        self.status = status
        self.headers = {} if headers is None else headers
        self.error = error
        self.calls = []
        self.read_calls = 0

    @contextmanager
    def stream(self, method, url, **options):
        self.calls.append((method, url, options))
        if self.error:
            raise self.error
        yield SimpleNamespace(status_code=self.status, headers=self.headers, iter_bytes=self.iter_bytes)

    def iter_bytes(self, chunk_size):
        self.read_calls += 1
        for offset in range(0, len(self.body), chunk_size):
            yield self.body[offset:offset + chunk_size]


class RecordedPolicyTransportTests(unittest.TestCase):
    def test_valid_historical_policy_only_is_returned_with_no_live_substitution(self):
        client = Client()
        result = fetch_recorded_policy(42, 'http://ai:8000/', client)
        self.assertEqual(result, payload())
        self.assertEqual(client.calls, [('GET', 'http://ai:8000/benchmark-traces/42/policy',
                                        {'timeout': 2.0, 'follow_redirects': False})])

    def test_older_ai_endpoint_not_supported_stays_unknown(self):
        result = fetch_recorded_policy(42, 'http://ai', Client(status=404))
        self.assertEqual(result['status'], 'not_recorded')
        self.assertEqual(result['reason'], 'unsupported_endpoint')
        self.assertIsNone(result['policy'])

    def test_ai_failure_and_redirect_are_unavailable_without_following(self):
        for code in (301, 302, 500, 503):
            result = fetch_recorded_policy(42, 'http://ai', Client(status=code))
            self.assertEqual(result['status'], 'unavailable')
            self.assertIsNone(result['policy'])

    def test_announced_oversize_is_rejected_before_body_read(self):
        for value in (str(RESPONSE_MAX_BYTES + 1), '-1', 'unknown'):
            client = Client(headers={'Content-Length': value})
            result = fetch_recorded_policy(42, 'http://ai', client)
            self.assertEqual(result['status'], 'invalid')
            self.assertEqual(client.read_calls, 0)

    def test_unannounced_oversize_and_malformed_json_are_bounded(self):
        for body in (b' ' * (RESPONSE_MAX_BYTES + 1), b'not json', b'\xff'):
            result = fetch_recorded_policy(42, 'http://ai', Client(body=body))
            self.assertEqual(result['status'], 'invalid')
            self.assertIsNone(result['policy'])

    def test_wrong_session_and_extra_untrusted_fields_are_not_forwarded(self):
        for change in ('session', 'secret'):
            data = payload()
            if change == 'session':
                data['session_id'] = 43
            else:
                data['raw_environment'] = 'private-token'
            result = fetch_recorded_policy(42, 'http://ai', Client(body=json.dumps(data).encode()))
            self.assertEqual(result['status'], 'invalid')
            self.assertNotIn('private-token', json.dumps(result))

    def test_tampered_policy_digest_is_invalid(self):
        data = payload()
        data['policy']['configuration']['detector']['confidence_threshold'] = .9
        self.assertEqual(fetch_recorded_policy(42, 'http://ai', Client(
            body=json.dumps(data).encode()))['status'], 'invalid')

    def test_nan_bool_as_number_and_string_config_are_rejected(self):
        for value in (float('nan'), True, 'secret-token'):
            data = payload()
            data['policy']['configuration']['detector']['confidence_threshold'] = value
            result = fetch_recorded_policy(42, 'http://ai', Client(body=json.dumps(data).encode()))
            self.assertEqual(result['status'], 'invalid')
            self.assertNotIn('secret-token', json.dumps(result))

    def test_unknown_field_and_incomplete_accounting_are_rejected_even_with_new_hash(self):
        for mode in ('unknown', 'missing'):
            policy = snapshot()
            if mode == 'unknown':
                policy['configuration']['worker']['unexpected_token'] = 'secret'
            else:
                del policy['configuration']['worker']['iou']
            body = {key: value for key, value in policy.items() if key != 'configuration_sha256'}
            policy['configuration_sha256'] = hashlib.sha256(json.dumps(
                body, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
            with self.assertRaises(ValueError):
                validate_policy(policy)

    def test_capture_failed_and_partial_absence_are_preserved(self):
        unavailable = policy_result(42, 'unavailable', 'capture_failed')
        result = fetch_recorded_policy(42, 'http://ai', Client(body=json.dumps(unavailable).encode()))
        self.assertEqual(result, unavailable)
        policy = snapshot()
        policy['component_presence']['primary'] = 'absent'
        del policy['configuration']['primary']
        policy['capture_status'] = 'partial'
        body = {key: value for key, value in policy.items() if key != 'configuration_sha256'}
        policy['configuration_sha256'] = hashlib.sha256(json.dumps(
            body, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
        data = payload()
        data['policy'] = policy
        result = fetch_recorded_policy(42, 'http://ai', Client(body=json.dumps(data).encode()))
        self.assertTrue(result['available'])
        self.assertNotIn('primary', result['policy']['configuration'])

    def test_network_exception_details_never_leave_the_helper(self):
        client = Client(error=RuntimeError('http://user:secret-token@private/path'))
        result = fetch_recorded_policy(42, 'http://ai', client)
        self.assertEqual(result['status'], 'unavailable')
        self.assertNotIn('secret', json.dumps(result))
        self.assertIsNone(result['runtime'])

    def test_validation_returns_detached_tree_without_mutating_input(self):
        original = snapshot()
        before = copy.deepcopy(original)
        result = validate_policy(original)
        result['configuration']['worker']['iou'] = .9
        self.assertEqual(original, before)

    def test_actual_backend_route_checks_existence_before_fetch_and_disables_cache(self):
        path = Path(__file__).parents[1] / 'app/api/routes.py'
        tree = ast.parse(path.read_text())
        node = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == 'benchmark_runtime_policy')
        node.decorator_list = []
        node.args.defaults = []
        for arg in node.args.args:
            arg.annotation = None
        node.returns = None
        class NotFound(Exception):
            def __init__(self, status_code, detail):
                self.status_code = status_code
        calls = []
        model = object()
        client = object()
        namespace = {'CountingBenchmark': model, 'HTTPException': NotFound,
                     'settings': SimpleNamespace(ai_service_url='http://ai'), 'httpx': client,
                     'fetch_recorded_policy': lambda *args: calls.append(args) or {'available': False}}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(path), 'exec'), namespace)
        response = SimpleNamespace(headers={})
        db = SimpleNamespace(get=lambda kind, identifier: None)
        with self.assertRaises(NotFound) as caught:
            namespace['benchmark_runtime_policy'](5, response, db)
        self.assertEqual(caught.exception.status_code, 404)
        self.assertEqual(calls, [])
        db.get = lambda kind, identifier: SimpleNamespace(session_id=42)
        self.assertEqual(namespace['benchmark_runtime_policy'](5, response, db), {'available': False})
        self.assertEqual(calls, [(42, 'http://ai', client)])
        self.assertEqual(response.headers['Cache-Control'], 'no-store')


if __name__ == '__main__':
    unittest.main()
