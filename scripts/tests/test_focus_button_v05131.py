"""V0.5.131: preserve native dark controls and panel focus button styling."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


class FocusButtonDarkRegression(unittest.TestCase):
    def test_focus_buttons_override_panel_defaults_without_important(self):
        css = (ROOT / 'frontend/src/styles.css').read_text(encoding='utf-8')
        start = css.index('/* V0.5.130: local read-only benchmark focus navigation */')
        fragment = css[start:]
        self.assertRegex(fragment, r'\.panel\s+button\.benchmark-focus-button\s*\{')
        self.assertIn('background:#132943', fragment)
        self.assertIn('border:1px solid #315274', fragment)
        self.assertIn('color:#cfe5ff', fragment)
        self.assertIn('.benchmark-focus-button:focus-visible', fragment)
        self.assertNotIn('!important', fragment)
        self.assertLess(css.index('.panel button{'), css.index('.panel button.benchmark-focus-button'))

    def test_backward_compatible_dark_control_contract(self):
        css = (ROOT / 'frontend/src/styles.css').read_text(encoding='utf-8')
        self.assertIn(':where(.app-shell, .auth-page) input:-webkit-autofill', css)
        self.assertIn('--traffic-field-bg: #0b1a2f;', css)
        self.assertNotIn('!important', css.split('/* V0.5.125: coherent native dark-mode controls')[1])
        jsx = (ROOT / 'frontend/src/main.jsx').read_text(encoding='utf-8')
        self.assertIn('className="secondary benchmark-focus-button"', jsx)
        self.assertIn('Ưu tiên xem bằng chứng V{APP_VERSION}', jsx)

    def test_release_local_only_migration_and_version_consistency(self):
        version = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
        self.assertRegex(version, r'^0\.5\.\d+$')
        self.assertGreaterEqual(int(version.split('.')[-1]), 131)
        package = json.loads((ROOT / 'frontend/package.json').read_text(encoding='utf-8'))
        self.assertEqual(package['version'], version)
        migration = (ROOT / 'backend/alembic/versions/0144_focus_css_v05131.py').read_text('utf-8')
        self.assertIn("revision = '0144_focus_css_v05131'", migration)
        self.assertIn("down_revision = '0143_local_trend_v05130'", migration)
        self.assertIn("value='0.5.131'", migration)
        self.assertIn("value='0.5.130'", migration)
        self.assertNotRegex(migration, r'(?im)\b(drop|create|alter|truncate)\s+table\b')
        self.assertFalse((ROOT / 'scripts/backup-gdrive.ps1').exists())
        self.assertEqual([p.name for p in ROOT.glob('*.md')], ['README.md'])

    def test_regression_runs_prior_to_frontend_build(self):
        ps = (ROOT / 'scripts/test.ps1').read_text('utf-8')
        self.assertIn('test_focus_button_v05131.py', ps)
        self.assertLess(ps.index('test_focus_button_v05131.py'), ps.index('Invoke-Step "Frontend build"'))
        self.assertNotIn('docker compose down -v', ps)


if __name__ == '__main__':
    unittest.main()
