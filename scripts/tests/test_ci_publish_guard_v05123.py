"""V0.5.123: CI runtime pins and GitHub release race regression (stdlib only)."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]

def src(path):
    return (ROOT / path).read_text('utf-8')

class CiPublishGuardV05123(unittest.TestCase):
    def test_all_workflows_match_nvmrc_and_docker(self):
        version = src('.nvmrc').strip()
        self.assertRegex(version, r'^\d+\.\d+\.\d+$')
        self.assertIn(f'FROM node:{version}-alpine', src('frontend/Dockerfile'))
        for rel in ('.github/workflows/ci.yml', '.github/workflows/release.yml', '.github/workflows/ci-release-reusable.yml'):
            content = src(rel)
            with self.subTest(workflow=rel):
                self.assertIn('actions/setup-node@v7', content)
                self.assertIn(f"node-version: '{version}'", content)
                self.assertIn('package-manager-cache: false', content)

    def test_test_ps1_uses_nvmrc_not_outdated_literal(self):
        script = src('scripts/test.ps1')
        self.assertIn('Get-Content (Join-Path $root ".nvmrc")', script)
        self.assertIn('$expectedNodeVersionLine', script)
        self.assertIn('$text.Contains($expectedNodeVersionLine)', script)
        self.assertIn('FROM node:$nodeVersion-alpine', script)
        self.assertNotIn("node-version: '26\\.10\\.0'", script)
        self.assertIn('CI + Node.js portability V0.5.10', script)

    def test_publish_rechecks_version_at_critical_boundaries(self):
        p = src('scripts/publish.ps1')
        self.assertIn('function Assert-ReleaseVersionStable', p)
        self.assertIn('function Assert-GitTreeReleaseVersion', p)
        for phase in ('sau kiểm thử, trước GitHub', 'trước git add', 'sau git commit', 'trước git push'):
            self.assertIn('Assert-ReleaseVersionStable -Phase "' + phase + '"', p)
        self.assertLess(p.index('Assert-ReleaseVersionStable -Phase "sau kiểm thử, trước GitHub"'), p.index('[BƯỚC 2/6]'))
        self.assertLess(p.index('Assert-ReleaseVersionStable -Phase "trước git add"'), p.index('git add -A'))
        self.assertLess(p.index('Assert-GitTreeReleaseVersion -Reference "refs/tags/$tag"'), p.index('git push -u origin'))
        self.assertIn('Assert-GitTreeReleaseVersion -Reference "INDEX"', p)
        self.assertIn('if ($Reference -eq "INDEX") { ":VERSION" }', p)
        self.assertIn('Assert-GitTreeReleaseVersion -Reference "HEAD"', p)
        self.assertIn('Assert-GitTreeReleaseVersion -Reference "refs/tags/$Tag"', p)
        for disallowed in ('git push --force', 'git tag -f', 'git reset --hard', 'docker compose down -v'):
            self.assertNotIn(disallowed, p)

    def test_release_metadata_is_consistent(self):
        version=src('VERSION').strip()
        self.assertRegex(version, r'^0\.5\.\d+$')
        self.assertEqual(json.loads(src('frontend/package.json'))['version'], version)
        self.assertIn("revision = '0137_ci_publish_guard_v05123'", src('backend/alembic/versions/0137_ci_publish_guard_v05123.py'))
        self.assertIn("down_revision = '0136_dependencies_v05122'", src('backend/alembic/versions/0137_ci_publish_guard_v05123.py'))
        self.assertIn("value='0.5.123'",src('backend/alembic/versions/0137_ci_publish_guard_v05123.py'))

if __name__ == '__main__':
    unittest.main()
