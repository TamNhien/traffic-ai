"""V0.5.113 frontend security pin and audit coverage (stdlib only)."""
import json
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAFE_VITE = (8, 3, 5)


def validate_vite_pin(package):
    vite = package.get("devDependencies", {}).get("vite")
    if not isinstance(vite, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", vite):
        return False
    return tuple(map(int, vite.split("."))) >= SAFE_VITE


class FrontendViteSecurityTests(unittest.TestCase):
    def package(self):
        return json.loads((ROOT / "frontend/package.json").read_text("utf-8"))

    def test_vite_dependency_pinned_to_safe_patch(self):
        self.assertEqual(self.package()["devDependencies"]["vite"], "8.3.5")
        self.assertTrue(validate_vite_pin(self.package()))

    def test_rejects_vulnerable_or_unpinned_versions(self):
        for version in ("8.3.0", "8.3.1", "8.3.2", "^8.3.0", "latest", "8.2.9", ""):
            with self.subTest(version=version):
                self.assertFalse(validate_vite_pin({"devDependencies": {"vite": version}}))

    def test_tech_contract_matches_safe_version(self):
        script = (ROOT / "scripts/test.ps1").read_text("utf-8")
        start = script.index("function Assert-TechnologyVersionsContract")
        end = script.index("function ", start + 15)
        self.assertIn('"vite": "8.3.5"', script[start:end])
        self.assertNotIn('"vite": "8.3.0"', script[start:end])

    def test_windows_and_docker_builds_remain_security_gated(self):
        script = (ROOT / "scripts/test.ps1").read_text("utf-8")
        dockerfile = (ROOT / "frontend/Dockerfile").read_text("utf-8")
        workflow = (ROOT / ".github/workflows/ci-release-reusable.yml").read_text("utf-8")
        for content in (script, dockerfile, workflow):
            self.assertIn("npm audit --audit-level=high", content)
        self.assertIn("npm run build", script)
        self.assertNotIn("npm audit --force", script)

    def test_security_tests_run_before_frontend_install(self):
        script = (ROOT / "scripts/test.ps1").read_text("utf-8")
        self.assertLess(script.index('V0.5.113 frontend Vite security pin'), script.index('Invoke-Step "Frontend build"'))
        self.assertIn("python -S -m unittest discover -s scripts/tests -p test_frontend_security_v05113.py", script)


if __name__ == "__main__":
    unittest.main()
