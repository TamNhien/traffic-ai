"""V0.5.124: npm pin consistency, legacy preflight drift regression (stdlib-only).

These checks are source-level verification only; Windows PowerShell and Docker
execution still need the actual scripts/test.ps1 run on the user's machine.
"""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
TARGETS = ('frontend/Dockerfile', '.github/workflows/ci.yml',
           '.github/workflows/ci-release-reusable.yml', '.github/workflows/release.yml')


def source(path):
    return (ROOT / path).read_text(encoding='utf-8')


def pinned_npm_versions(content):
    return set(re.findall(r'npm@\d+\.\d+\.\d+', content))


class DynamicNpmPreflightTests(unittest.TestCase):
    def test_current_manifest_is_single_source_of_truth_for_every_installer(self):
        expected = json.loads(source('frontend/package.json'))['packageManager']
        self.assertRegex(expected, r'^npm@\d+\.\d+\.\d+$')
        for target in TARGETS:
            with self.subTest(file=target):
                self.assertEqual(pinned_npm_versions(source(target)), {expected})

    def test_legacy_contract_uses_manifest_not_hardcoded_old_pin(self):
        script = source('scripts/test.ps1')
        legacy = script.split('function Assert-ObservedPathCleanFrameV0552Contract {', 1)[1].split('function Assert-CandidateEvidenceV0553Contract {', 1)[0]
        self.assertIn('$expectedNpm = [string]$package.packageManager', legacy)
        self.assertIn('$pins.Count -ne 1 -or $pins[0] -cne $expectedNpm', legacy)
        self.assertIn("[regex]::Matches($text, 'npm@\\d+\\.\\d+\\.\\d+')", legacy)
        self.assertNotIn("-notmatch 'npm@12\\.2\\.0'", legacy)
        self.assertNotIn('npm@12.1.0', legacy)
        self.assertNotIn('npm@12.2.0', legacy)
        for target in TARGETS:
            self.assertIn(target.replace('/', '\\'), legacy)

    def test_mismatch_and_multiple_pins_fail_closed(self):
        expected = 'npm@12.2.1'
        valid = 'RUN npm install -g npm@12.2.1'
        self.assertEqual(pinned_npm_versions(valid), {expected})
        self.assertNotEqual(pinned_npm_versions(valid.replace('12.2.1', '12.1.0')), {expected})
        self.assertNotEqual(pinned_npm_versions(valid + ' npm@12.2.0'), {expected})
        self.assertNotEqual(pinned_npm_versions('npm install -g npm'), {expected})

    def test_pixel_regression_numpy_pin_is_not_stale(self):
        script = source('scripts/test.ps1')
        legacy = script.split('function Assert-ObservedPathCleanFrameV0552Contract {', 1)[1].split('function Assert-CandidateEvidenceV0553Contract {', 1)[0]
        requirements = source('ai-service/requirements-test.txt')
        self.assertEqual(len(re.findall(r'^numpy==\d+\.\d+\.\d+\s*$', requirements, re.M)), 1)
        self.assertIn("[regex]::Matches($aiRequirements, '(?m)^numpy==\\d+\\.\\d+\\.\\d+\\s*$')", legacy)
        self.assertNotIn('numpy==2\\.4\\.6', legacy)

    def test_version_migration_does_not_change_business_tables(self):
        version = source('VERSION').strip()
        self.assertRegex(version, r'^0\.5\.\d+$')
        self.assertEqual(json.loads(source('frontend/package.json'))['version'], version)
        migration = source('backend/alembic/versions/0138_npm_contract_v05124.py')
        self.assertIn("revision = '0138_npm_contract_v05124'", migration)
        self.assertIn("down_revision = '0137_ci_publish_guard_v05123'", migration)
        self.assertIn("value='0.5.124'", migration)
        self.assertIn("value='0.5.123'", migration)
        self.assertNotRegex(migration, r'(?im)\b(drop|truncate|alter|create)\s+table\b')

    def test_release_runner_executes_new_regression_before_frontend_install(self):
        script = source('scripts/test.ps1')
        self.assertIn('test_npm_preflight_v05124.py', script)
        self.assertLess(script.index('test_npm_preflight_v05124.py'), script.index('Invoke-Step "Frontend build"'))
        self.assertIn('npm audit --audit-level=high', script)
        self.assertNotIn('npm audit --force', script)
        self.assertNotIn('docker compose down -v', script)


if __name__ == '__main__':
    unittest.main()
