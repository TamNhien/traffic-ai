"""Real-interpreter regressions for release overlays with unchanged ZIP times.

Each test uses a disposable source directory and actual child Python processes.
It never removes or imports bytecode from the user's project or installed apps.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
STAMP = 1_582_934_400
OLD_SOURCE = "VERSION = '0.5.94'\n"
NEW_SOURCE = "VERSION = '0.5.95'\n"
IMPORT_PROBE = (
    "import json,sys,release_probe; "
    "print(json.dumps({'version': release_probe.VERSION, "
    "'cached': release_probe.__cached__, "
    "'prefix': sys.pycache_prefix, "
    "'no_write': sys.dont_write_bytecode}))"
)


class PythonReleaseCacheRegression(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="traffic-ai-pycache-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / "release_probe.py"
        self.environment = os.environ.copy()
        # The test runner itself uses the production cache policy. Child probes
        # must first reproduce the old behavior independently of that policy.
        for key in ("PYTHONPYCACHEPREFIX", "PYTHONDONTWRITEBYTECODE", "PYTHONPATH"):
            self.environment.pop(key, None)
        self.write_source(OLD_SOURCE)

    def write_source(self, contents):
        self.source.write_bytes(contents.encode("utf-8"))
        os.utime(self.source, (STAMP, STAMP))

    def run_python(self, arguments, environment=None):
        result = subprocess.run(
            [sys.executable, *arguments],
            cwd=self.root,
            env=self.environment if environment is None else environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def probe(self, environment=None, flags=()):
        return json.loads(self.run_python([*flags, "-c", IMPORT_PROBE], environment))

    def seed_old_cache_and_overlay(self):
        old = self.probe()
        self.assertEqual(old["version"], "0.5.94")
        cache = Path(old["cached"])
        self.assertTrue(cache.is_file(), "the child must actually create bytecode")
        before = hashlib.sha256(cache.read_bytes()).hexdigest()
        old_metadata = (self.source.stat().st_mtime_ns, self.source.stat().st_size)
        self.write_source(NEW_SOURCE)
        self.assertEqual(
            (self.source.stat().st_mtime_ns, self.source.stat().st_size),
            old_metadata,
            "release overlay must preserve both timestamp and byte length",
        )
        return cache, before

    def test_same_timestamp_and_size_can_import_previous_release(self):
        self.seed_old_cache_and_overlay()
        self.assertIn("0.5.95", self.source.read_text("utf-8"))
        self.assertEqual(self.probe()["version"], "0.5.94")

    def test_B_flag_still_reads_existing_stale_bytecode(self):
        self.seed_old_cache_and_overlay()
        result = self.probe(flags=("-B",))
        self.assertTrue(result["no_write"])
        self.assertEqual(result["version"], "0.5.94")

    def test_no_write_environment_still_reads_existing_stale_bytecode(self):
        self.seed_old_cache_and_overlay()
        environment = {**self.environment, "PYTHONDONTWRITEBYTECODE": "1"}
        result = self.probe(environment)
        self.assertTrue(result["no_write"])
        self.assertEqual(result["version"], "0.5.94")

    def test_fresh_prefix_imports_current_source_without_touching_host_cache(self):
        cache, before = self.seed_old_cache_and_overlay()
        prefix = self.root / "container-temporary-cache"
        environment = {
            **self.environment,
            "PYTHONPYCACHEPREFIX": str(prefix),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        result = self.probe(environment)
        self.assertEqual(result["version"], "0.5.95")
        self.assertEqual(Path(result["prefix"]), prefix)
        self.assertTrue(Path(result["cached"]).is_relative_to(prefix))
        self.assertTrue(result["no_write"])
        self.assertEqual(hashlib.sha256(cache.read_bytes()).hexdigest(), before)
        self.assertFalse(list(prefix.rglob("*.pyc")))

    def test_compileall_uses_prefix_even_when_no_write_is_enabled(self):
        cache, before = self.seed_old_cache_and_overlay()
        prefix = self.root / "compile-container-cache"
        environment = {
            **self.environment,
            "PYTHONPYCACHEPREFIX": str(prefix),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        # compileall explicitly creates .pyc despite PYTHONDONTWRITEBYTECODE.
        # Its destination must therefore be isolated as well as normal imports.
        self.run_python(["-m", "compileall", "-q", str(self.source)], environment)
        result = self.probe(environment)
        self.assertEqual(result["version"], "0.5.95")
        self.assertTrue(Path(result["cached"]).is_relative_to(prefix))
        self.assertTrue(Path(result["cached"]).is_file())
        self.assertEqual(hashlib.sha256(cache.read_bytes()).hexdigest(), before)
        self.assertEqual(list(self.root.glob("__pycache__/release_probe*.pyc")), [cache])

    def test_container_cache_must_be_fresh_for_each_container(self):
        first_prefix = self.root / "first-container-tmp"
        first_environment = {
            **self.environment,
            "PYTHONPYCACHEPREFIX": str(first_prefix),
        }
        self.assertEqual(self.probe(first_environment)["version"], "0.5.94")
        self.write_source(NEW_SOURCE)
        self.assertEqual(self.probe(first_environment)["version"], "0.5.94")
        next_environment = {
            **self.environment,
            "PYTHONPYCACHEPREFIX": str(self.root / "next-container-tmp"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        self.assertEqual(self.probe(next_environment)["version"], "0.5.95")


class PythonDockerCacheCoverage(unittest.TestCase):
    def test_every_python_test_container_has_private_cache_environment(self):
        test_script = (ROOT / "scripts/test.ps1").read_text("utf-8")
        logical_lines = re.sub(r"`[ \t]*\r?\n", " ", test_script)
        commands = re.findall(r"(?m)^\s*docker run --rm[^\n]+", logical_lines)
        python_commands = [line for line in commands if "python:3.14.7-slim" in line]
        self.assertGreaterEqual(len(python_commands), 20)
        for command in python_commands:
            with self.subTest(command=command.strip()[:150]):
                self.assertIn("-e PYTHONPYCACHEPREFIX=/tmp/traffic-ai-test-pycache", command)
                self.assertIn("-e PYTHONDONTWRITEBYTECODE=1", command)
                self.assertLess(command.index("PYTHONPYCACHEPREFIX="), command.index("python:3.14.7-slim"))
                self.assertNotRegex(command, r"-v\s+\S*traffic-ai-test-pycache")

    def test_real_cache_regression_runs_in_normal_test_command(self):
        text = (ROOT / "scripts/test.ps1").read_text("utf-8")
        self.assertIn("-p test_python_cache_v0596.py -v", text)
        self.assertLess(text.index("Assert-TrafficDockerEngine\n"), text.index("-p test_python_cache_v0596.py -v"))


if __name__ == "__main__":
    unittest.main()
