"""Regression for a missing host Python command in the V0.5.127 test runner."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def block(source, title):
    prefix = 'Invoke-Step "' + title + '" {'
    start = source.index(prefix)
    end = source.index('\n}', start)
    return source[start:end+2]


class IsolatedRepeatabilityRunnerTests(unittest.TestCase):
    def test_original_repeatability_runner_uses_docker_not_undefined_host_python(self):
        test_script = (ROOT / 'scripts/test.ps1').read_text('utf-8')
        section = block(test_script, 'V0.5.127 verified repeatability regression (stdlib-only)')
        self.assertNotIn('$python.Source', section)
        for required in ('docker run --rm', 'PYTHONPYCACHEPREFIX=/tmp/traffic-ai-test-pycache',
                         '-v "${root}:/src"', '-w /src python:3.14.10-slim',
                         'python -B -m unittest discover -s scripts/tests -p test_benchmark_repeatability_v05127.py -v',
                         'if ($LASTEXITCODE -ne 0)'):
            with self.subTest(required=required):
                self.assertIn(required, section)

    def test_runner_regression_is_wired_before_frontend_build(self):
        test_script = (ROOT / 'scripts/test.ps1').read_text('utf-8')
        section = block(test_script, 'V0.5.128 isolated repeatability runner regression (stdlib-only)')
        self.assertIn('docker run --rm', section)
        self.assertIn('test_repeatability_runner_v05128.py', section)
        self.assertIn('if ($LASTEXITCODE -ne 0)', section)
        self.assertLess(test_script.index('test_repeatability_runner_v05128.py'),
                        test_script.index('test_benchmark_repeatability_v05127.py'))
        self.assertLess(test_script.index('test_benchmark_repeatability_v05127.py'),
                        test_script.index('Invoke-Step "Backend unit tests"'))

    def test_current_version_and_metadata_only_migration(self):
        self.assertEqual((ROOT / 'VERSION').read_text('utf-8').strip(), '0.5.128')
        migration = (ROOT / 'backend/alembic/versions/0142_repeatability_runner_v05128.py').read_text('utf-8')
        self.assertIn("down_revision = '0141_repeatability_v05127'", migration)
        self.assertIn("value='0.5.128'", migration)
        self.assertNotIn('ALTER TABLE', migration.upper())
        self.assertEqual([x.name for x in ROOT.glob('*.md')], ['README.md'])

    def test_no_mutating_operations_in_repeatability_tool(self):
        tool = (ROOT / 'scripts/audit-benchmark-repeatability.py').read_text('utf-8')
        for unsafe in ('docker compose down -v', 'os.remove(', 'shutil.rmtree(', 'DELETE FROM'):
            self.assertNotIn(unsafe, tool)


if __name__ == '__main__':
    unittest.main()
