import gzip
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

SCRIPT = Path(__file__).resolve().parents[1] / 'benchmark-forensics.py'
spec = importlib.util.spec_from_file_location('benchmark_forensics', SCRIPT)
forensics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(forensics)


def export(path: Path, *, with_trace=True, corrupt_trace=False, broken_footer=False):
    report = {
        'report_readiness': {'scoring_available': True},
        'benchmark': {'id': 4}, 'session_id': 8,
        'ground_truth_total': 2, 'ai_total': 2,
        'matched': 1, 'missed': 1, 'false_positives': 1,
        'matched_items': [{'ground_truth_id': 1, 'ai_event_id': 11}],
        'missed_items': [{'ground_truth_id': 2, 'time': 10.0, 'direction': 'in', 'vehicle_type': 'motorcycle'}],
        'false_positive_items': [{'ai_event_id': 12, 'time': 10.08, 'direction': 'in', 'vehicle_type': 'motorcycle',
                                  'reason': 'rescued_gap_unmatched'}],
        'integrity': {'ok': True},
    }
    data = {'report.json': report, 'ground-truth.json': [
        {'id': 1, 'source_time_seconds': 2.0, 'direction': 'in', 'vehicle_type': 'motorcycle'},
        {'id': 2, 'source_time_seconds': 10.0, 'direction': 'in', 'vehicle_type': 'motorcycle'}],
        'events.json': [{'id': 11}, {'id': 12}], 'session.json': {'id': 8}, 'config.json': {}}
    content = {name: (json.dumps(value) + '\n').encode() for name, value in data.items()}
    trace = [
        {'kind': 'session_metadata', 'source_fps': 25, 'source_frame_count': 4},
        {'kind': 'geometry_metadata', 'line': [[.1,.2],[.7,.8]]},
        {'camera_id': 1, 'session_id': 8, 'frame_index': 1, 'source_time_seconds': 9.92,
         'gate_tracks': [{'track_id': 32, 'label': 'motorcycle', 'anchor_signed': -0.02}],
         'class_refine_decision_audit': [{'kind': 'class_refinement'}]},
        {'camera_id': 1, 'session_id': 8, 'frame_index': 2, 'source_time_seconds': 10.02,
         'gate_tracks': [{'track_id': 32, 'label': 'motorcycle', 'anchor_signed': .03}],
         'crossing_proposals': [{'tracking_id': 32, 'source_time_seconds': 10.02, 'direction': 'in', 'crossing_method': 'direct'}]},
        {'camera_id': 1, 'session_id': 8, 'source_time_seconds': 10.08, 'kind': 'event_delivery',
         'outcome': 'created', 'backend_event_id': 12, 'tracking_id': 32, 'crossing_method': 'rescued', 'direction': 'in'},
        {'kind': 'delivery_summary', 'delivery_drain_complete': not broken_footer, 'pending_events': 0},
    ]
    source = ('\n'.join(json.dumps(item, separators=(',', ':')) for item in trace) + '\n').encode()
    compressed = gzip.compress(source, mtime=0)
    trace_name = 'benchmark-trace.jsonl.gz'
    if with_trace:
        content[trace_name] = compressed
    manifest = {'format': 'traffic-ai-benchmark-diagnostics', 'schema_version': 1,
                'files': {name: {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
                          for name, raw in content.items()},
                'trace': {'available': with_trace, 'reason': 'available' if with_trace else 'missing',
                          'closed': with_trace, 'source_sha256': hashlib.sha256(source).hexdigest(),
                          'source_bytes': len(source)}}
    if corrupt_trace:
        manifest['files'][trace_name]['sha256'] = '0' * 64
    content['manifest.json'] = json.dumps(manifest).encode()
    with ZipFile(path, 'w') as z:
        for name, raw in content.items():
            z.writestr(name, raw)


class BenchmarkForensicsTests(unittest.TestCase):
    def test_with_verified_trace_nearby_two_sided_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'benchmark.zip'
            export(p)
            result = forensics.analyze(p)
            self.assertEqual((result['missed'], result['extra']), (1, 1))
            self.assertTrue(result['trace_available'])
            self.assertEqual(result['cases'][0]['trace_evidence']['tracks_both_sides'], 1)
            self.assertEqual(result['cases'][1]['trace_evidence']['frames'], 2)
            self.assertIn('Audit only', forensics.format_markdown(result))

    def test_missing_trace_retains_verified_backend_cases_without_fake_frame_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'benchmark.zip'
            export(p, with_trace=False)
            result = forensics.analyze(p)
            self.assertFalse(result['trace_available'])
            self.assertNotIn('trace_evidence', result['cases'][0])

    def test_reject_corrupt_trace_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'benchmark.zip'
            export(p, corrupt_trace=True)
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                forensics.analyze(p)

    def test_reject_trace_without_closed_delivery_footer(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'benchmark.zip'
            export(p, broken_footer=True)
            with self.assertRaisesRegex(ValueError, 'delivery summary'):
                forensics.analyze(p)

    def test_reject_invalid_review_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'benchmark.zip'
            export(p)
            with self.assertRaises(ValueError):
                forensics.analyze(p, margin=9.0)

    def test_command_writes_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'benchmark.zip'
            export(p)
            target = Path(tmp) / 'reports'
            self.assertEqual(forensics.main(['--export', str(p), '--output-dir', str(target)]), 0)
            self.assertEqual(json.loads((target / 'cases.json').read_text())['extra'], 1)
            self.assertIn('Session #8', (target / 'cases.md').read_text())


if __name__ == '__main__':
    unittest.main()
