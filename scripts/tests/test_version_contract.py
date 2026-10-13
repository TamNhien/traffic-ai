"""V0.5.79: version mismatch must be caught before publishing a build."""
import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2]
SCRIPT = SOURCE / 'scripts/version-contract.py'
spec = importlib.util.spec_from_file_location('version_contract', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class VersionMetadataTests(unittest.TestCase):
    def test_source_is_consistent(self):
        self.assertEqual([], module.check(SOURCE))

    def _isolated_release_fixture(self, dest):
        paths = [
            'VERSION', 'frontend/package.json', 'frontend/src/main.jsx',
            'frontend/index.html', 'backend/app/main.py',
            'backend/app/backup_routes.py', 'ai-service/app/main.py',
            'backup-worker/worker.py', 'scripts/test.ps1'
        ]
        paths += [str(p.relative_to(SOURCE)) for p in (SOURCE / 'backend/alembic/versions').glob('*.py')]
        for rel in paths:
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SOURCE / rel, target)

    def test_stale_hardcoded_powershell_version_is_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._isolated_release_fixture(root)
            guard = root / 'scripts/test.ps1'
            text = guard.read_text('utf-8')
            start = text.index('function Assert-VersionConsistencyContract {')
            insertion = text.index('  $package = Get-Content', start)
            guard.write_text(text[:insertion] + '  if ($version -ne "0.5.77") { throw "stale" }\n' + text[insertion:], encoding='utf-8')
            self.assertTrue(any('pins current version' in e for e in module.check(root)))

    def test_outdated_frontend_package_is_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._isolated_release_fixture(root)
            package = root / 'frontend/package.json'
            version = (root / 'VERSION').read_text('utf-8').strip()
            package.write_text(package.read_text('utf-8').replace(f'"version": "{version}"', '"version": "0.5.77"'), encoding='utf-8')
            self.assertTrue(any('frontend/package.json' in e for e in module.check(root)))

    def test_long_migration_revision_is_detected_before_windows_powershell(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._isolated_release_fixture(root)
            head = root / 'backend/alembic/versions/0102_temporal_review_v0588.py'
            old = '0102_temporal_review_v0588'
            oversized = '0102_temporal_review_contract_v0588'
            head.write_text(head.read_text('utf-8').replace(old, oversized), encoding='utf-8')
            self.assertTrue(any('Alembic revision too long' in e for e in module.check(root)))

    def test_current_head_matches_release(self):
        self.assertEqual([], module.check(SOURCE))
        self.assertIn('0093_version_contract_v0579', (SOURCE / 'backend/alembic/versions/0093_version_contract_v0579.py').read_text('utf-8'))


if __name__ == '__main__':
    unittest.main()
