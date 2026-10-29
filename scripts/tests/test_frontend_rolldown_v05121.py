"""V0.5.121: pin the Rolldown version that Vite 8.3.5 can actually install.

A floating Vite transitive range selected the unavailable Rolldown 1.2.16
on 2026-10-29. These offline guards ensure normal installers are protected
without lowering the Vite security baseline or skipping npm audit.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUPPORTED_VITE = "8.3.5"
ROLLDOWN_VERSION = "1.2.15"


def accepts_rolldown_pin(package):
    deps = package.get("devDependencies", {})
    overrides = package.get("overrides", {})
    if not isinstance(deps, dict) or not isinstance(overrides, dict):
        return False
    return (
        deps.get("vite") == SUPPORTED_VITE
        and overrides.get("rolldown") == ROLLDOWN_VERSION
        and bool(re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", overrides["rolldown"]))
    )


class FrontendRolldownReleaseTests(unittest.TestCase):
    def package(self):
        return json.loads((ROOT / "frontend/package.json").read_text("utf-8"))

    def test_actual_package_pins_available_compatible_rolldown(self):
        package = self.package()
        self.assertTrue(accepts_rolldown_pin(package))
        self.assertEqual("1.2.2", package["overrides"]["source-map-js"])

    def test_unavailable_float_or_weaker_override_rejected(self):
        for value in (None, "1.2.16", "^1.2.14", "~1.2.14", "latest", "1.2.14 "):
            with self.subTest(value=value):
                p = self.package()
                if value is None:
                    p["overrides"].pop("rolldown")
                else:
                    p["overrides"]["rolldown"] = value
                self.assertFalse(accepts_rolldown_pin(p))

    def test_installs_use_project_manifest_and_keep_security_gate(self):
        ps = (ROOT / "scripts/test.ps1").read_text("utf-8")
        df = (ROOT / "frontend/Dockerfile").read_text("utf-8")
        ci = (ROOT / ".github/workflows/ci-release-reusable.yml").read_text("utf-8")
        self.assertIn("npm install && npm test && npm audit --audit-level=high && npm run build", ps)
        self.assertIn("npm install", df)
        self.assertIn("npm audit --audit-level=high", df)
        self.assertIn("npm install", ci)
        self.assertIn("npm audit --audit-level=high", ci)
        for content in (ps, df, ci):
            self.assertNotIn("--legacy-peer-deps", content)
            self.assertNotIn("npm audit --force", content)

    def test_regression_is_wired_before_frontend_build(self):
        ps = (ROOT / "scripts/test.ps1").read_text("utf-8")
        label = 'V0.5.121 frontend Rolldown registry availability (stdlib-only)'
        self.assertIn(label, ps)
        self.assertIn("test_frontend_rolldown_v05121.py", ps)
        self.assertLess(ps.index(label), ps.index('Invoke-Step "Frontend build"'))

    def test_frontend_runtime_unchanged_except_release_number(self):
        package = self.package()
        self.assertEqual("19.3.1", package["dependencies"]["react"])
        self.assertEqual("19.3.1", package["dependencies"]["react-dom"])
        self.assertEqual("6.1.2", package["devDependencies"]["@vitejs/plugin-react"])


if __name__ == "__main__":
    unittest.main()
