"""Prevent calling uninstalled pytest in a bare python:slim Docker regression."""
from pathlib import Path
import os
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]


class EndpointRunnerRegression(unittest.TestCase):
    def test_release_runner_uses_stdlib_without_pip(self):
        source = (ROOT / 'scripts/test.ps1').read_text(encoding='utf-8')
        start = source.index('Invoke-Step "V0.5.106 finite endpoint precision regression (stdlib-only)"')
        stop = source.index('Invoke-Step "V0.5.107 pytest-free endpoint runner contract', start)
        block = source[start:stop]
        self.assertIn('python:3.14.7-slim', block)
        self.assertIn('python -S -m unittest discover -s tests -p test_finite_endpoint_guard_v05106.py -v', block)
        self.assertNotIn('python -m pytest', block)
        self.assertNotIn('pip install', block)
        self.assertIn('if ($LASTEXITCODE -ne 0)', block)

    def test_endpoint_tests_run_with_site_packages_disabled(self):
        env = dict(os.environ)
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        result = subprocess.run(
            [sys.executable, '-S', '-m', 'unittest', 'discover', '-s', 'tests',
             '-p', 'test_finite_endpoint_guard_v05106.py', '-v'],
            cwd=ROOT / 'ai-service', env=env,
            capture_output=True, text=True, timeout=25,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Ran 3 tests', result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
