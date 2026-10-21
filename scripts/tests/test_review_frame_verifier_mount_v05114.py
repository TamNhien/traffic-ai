"""V0.5.114: review-frame verifier's nested Docker mount dependency contract."""
from __future__ import annotations

import importlib.util
import json
import re
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"


class ReviewFrameVerifierMountTests(unittest.TestCase):
    def test_every_transitive_verifier_is_bind_mounted_read_only(self):
        ps = (SCRIPTS / 'export-benchmark-review-frames.ps1').read_text(encoding='utf-8')
        for name in ('benchmark-forensics.py', 'benchmark-gate.py'):
            self.assertIn(f"${{verifier}}:/opt/{name}:ro" if name == 'benchmark-forensics.py'
                          else f"${{gateVerifier}}:/opt/{name}:ro", ps)
        self.assertIn("${tool}:/opt/review-tool.py:ro", ps)
        self.assertIn("${gateVerifier}:/opt/benchmark-gate.py:ro", ps)
        self.assertIn('Test-Path -LiteralPath $required -PathType Leaf', ps)
        self.assertIn("'--entrypoint','python','ai-service'", ps)
        # Tools must NOT be baked into the running AI image, and all mounts must be read-only.
        for name in ('benchmark-forensics.py', 'benchmark-gate.py'):
            self.assertTrue((SCRIPTS / name).is_file())
        self.assertNotIn('pip install', ps)

    def test_relative_import_chain_needs_benchmark_gate_sibling(self):
        exporter = (SCRIPTS / 'export-benchmark-review-frames.py').read_text('utf-8')
        forensics = (SCRIPTS / 'benchmark-forensics.py').read_text('utf-8')
        self.assertIn("with_name('benchmark-forensics.py')", exporter)
        self.assertIn("with_name('benchmark-gate.py')", forensics)
        # The source locations mirror /opt mount targets, catching filename mismatches.
        self.assertIn("/opt/benchmark-forensics.py:ro", (SCRIPTS/'export-benchmark-review-frames.ps1').read_text())
        self.assertIn("/opt/benchmark-gate.py:ro", (SCRIPTS/'export-benchmark-review-frames.ps1').read_text())

    def test_python_loader_resolves_full_sibling_chain_in_isolation(self):
        # Simulate the three explicit read-only mounts without Docker and with no cv2.
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder)
            for name in ('export-benchmark-review-frames.py', 'benchmark-forensics.py', 'benchmark-gate.py'):
                (temp / name).write_bytes((SCRIPTS / name).read_bytes())
            spec = importlib.util.spec_from_file_location('mounted_review_tool', temp / 'export-benchmark-review-frames.py')
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            # Missing archive should be diagnosed by the genuine benchmark gate,
            # not by a FileNotFoundError for the verifier file itself.
            with self.assertRaisesRegex(ValueError, 'Benchmark ZIP not found'):
                mod.verified_cases(temp / 'missing.zip')

    def test_read_only_review_never_changes_ground_truth_or_counting(self):
        shell = (SCRIPTS/'export-benchmark-review-frames.ps1').read_text('utf-8')
        self.assertIn('/mnt/benchmark.zip:ro', shell)
        self.assertIn('/mnt/input.mp4:ro', shell)
        self.assertNotIn('docker compose up', shell)


if __name__ == '__main__':
    unittest.main()
