"""V0.5.111: distinguish missing Downloads ZIP from corrupted/valid exports.

All tests use Python stdlib and must leave GT, events and source ZIP unchanged.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[2]


def module(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def make_small_export(path):
    rows = {'report.json': {
        'benchmark': {'id': 80}, 'session_id': 207,
        'report_readiness': {'scoring_available': True},
        'ground_truth_total': 1, 'ai_total': 1, 'matched': 1,
        'missed': 0, 'false_positives': 0,
        'matched_items': [{}], 'missed_items': [], 'false_positive_items': [],
        'integrity': {'ok': True}, 'tolerance_seconds': 0.75,
    }, 'ground-truth.json': [
        {'source_time_seconds': 1.0, 'direction': 'in', 'vehicle_type': 'motorcycle'}
    ], 'events.json': [{}], 'session.json': {}, 'config.json': {}}
    encoded = {name: json.dumps(value, ensure_ascii=False).encode('utf-8') for name, value in rows.items()}
    manifest = {'format': 'traffic-ai-benchmark-diagnostics', 'schema_version': 1,
                'files': {key: {'bytes': len(value), 'sha256': hashlib.sha256(value).hexdigest()}
                          for key, value in encoded.items()}}
    with ZipFile(path, 'w', ZIP_DEFLATED) as z:
        for name, raw in encoded.items():
            z.writestr(name, raw)
        z.writestr('manifest.json', json.dumps(manifest))


class ZipPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gate = module('benchmark_gate_zip_111', 'scripts/benchmark-gate.py')
        cls.audit = module('audit_gate_zip_111', 'scripts/audit-gate-coverage.py')

    def test_missing_zip_identifies_absolute_path_and_action(self):
        with tempfile.TemporaryDirectory() as d:
            missing = Path(d) / 'traffic-ai-benchmark-80-session-207-recovered-v110.zip'
            with self.assertRaisesRegex(self.gate.BenchmarkEvidenceError, 'Benchmark ZIP not found:') as info:
                self.gate.load_evidence(missing)
            self.assertIn(str(missing), str(info.exception))
            self.assertIn('full absolute path', str(info.exception))

    def test_directory_is_not_claimed_corrupt(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(self.gate.BenchmarkEvidenceError, 'not a file'):
                self.gate.load_evidence(d)

    def test_invalid_download_is_different_from_missing(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'download.zip'
            p.write_bytes(b'Not actually a ZIP')
            with self.assertRaisesRegex(self.gate.BenchmarkEvidenceError, 'Invalid/truncated'):
                self.gate.load_evidence(p)

    def test_partially_written_zip_is_distinguished(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'half.zip'
            make_small_export(p)
            p.write_bytes(p.read_bytes()[:200])
            with self.assertRaisesRegex(self.gate.BenchmarkEvidenceError, 'Invalid/truncated'):
                self.gate.load_evidence(p)

    def test_valid_zip_and_all_original_bytes_stay_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'ok.zip'
            make_small_export(p)
            old = p.read_bytes()
            report, manifest = self.gate.load_evidence(p)
            self.assertEqual(report['session_id'], 207)
            self.assertEqual(manifest['format'], 'traffic-ai-benchmark-diagnostics')
            self.assertEqual(p.read_bytes(), old)

    def test_incomplete_export_gets_semantic_message_not_corruption(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'incomplete.zip'
            with ZipFile(p, 'w') as z:
                z.writestr('manifest.json', '{}')
            with self.assertRaisesRegex(self.gate.BenchmarkEvidenceError, 'Not a complete'):
                self.gate.load_evidence(p)

    def test_audit_missing_zip_fails_without_creating_output(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / 'absent.zip'
            report_folder = Path(d) / 'out'
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code = self.audit.main(['--export', str(source), '--output-dir', str(report_folder)])
            self.assertEqual(code, 2)
            self.assertIn('Benchmark ZIP not found:', stderr.getvalue())
            self.assertFalse(report_folder.exists())

    def test_powershell_uses_literal_path_and_passes_resolved_filename(self):
        ps = (ROOT / 'scripts/audit-gate-coverage.ps1').read_text(encoding='utf-8')
        self.assertIn('Get-Item -LiteralPath $Export', ps)
        self.assertIn('$benchmarkFile.FullName', ps)
        self.assertIn('đường dẫn tuyệt đối', ps)
        self.assertNotIn("'--export', $Export", ps)


if __name__ == '__main__':
    unittest.main()
