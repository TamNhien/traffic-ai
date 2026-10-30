"""V0.5.125 dark controls source contract (Python stdlib, offline-safe)."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


def source(name):
    return (ROOT / name).read_text(encoding='utf-8')


class DarkControlsContract(unittest.TestCase):
    def setUp(self):
        css = source('frontend/src/styles.css')
        self.assertIn('/* V0.5.125: coherent native dark-mode controls', css)
        self.theme = css.split('/* V0.5.125: coherent native dark-mode controls')[1]

    def test_dark_theme_covers_signed_in_and_signed_out_forms(self):
        self.assertIn(':where(.app-shell, .auth-page)', self.theme)
        self.assertRegex(self.theme, r'color-scheme:\s*dark')
        for kind in ('input', 'select', 'textarea'):
            self.assertIn(kind, self.theme)
        self.assertIn('select :is(option, optgroup)', self.theme)

    def test_neutral_fields_keep_native_control_types_intact(self):
        for name in ('checkbox','radio','range','file','hidden','button','submit','reset','color'):
            self.assertIn(f':not([type="{name}"])', self.theme)
        self.assertIn('accent-color: #2dd4bf', self.theme)

    def test_accessible_focus_placeholder_and_autofill_are_styled(self):
        for phrase in ('::placeholder', ':focus-visible', 'input:-webkit-autofill',
                       '-webkit-text-fill-color', '-webkit-box-shadow', 'caret-color'):
            self.assertIn(phrase, self.theme)
        self.assertNotIn('!important', self.theme)

    def test_dataset_finetune_and_login_exist_and_do_not_need_js_changes(self):
        ui = source('frontend/src/main.jsx')
        security = source('frontend/src/security.jsx')
        for name in ('dataset-form', 'train-form', 'dataset-select'):
            self.assertIn(name, ui)
        self.assertTrue('auth-page' in ui or 'auth-page' in security)

    def test_version_and_migration_only_update_metadata(self):
        version = source('VERSION').strip()
        self.assertRegex(version, r'^0\.5\.\d+$')
        self.assertEqual(json.loads(source('frontend/package.json'))['version'], version)
        migration = source('backend/alembic/versions/0139_dark_inputs_v05125.py')
        for text in ("revision = '0139_dark_inputs_v05125'",
                     "down_revision = '0138_npm_contract_v05124'",
                     "value='0.5.125'", "value='0.5.124'"):
            self.assertIn(text, migration)
        self.assertNotRegex(migration, r'(?im)\b(drop|create|alter|truncate)\s+table\b')

    def test_preflight_runs_before_frontend_install(self):
        script = source('scripts/test.ps1')
        self.assertIn('test_dark_controls_v05125.py', script)
        self.assertLess(script.index('test_dark_controls_v05125.py'),script.index('Invoke-Step "Frontend build"'))
        self.assertIn('npm audit --audit-level=high', script)
        self.assertNotIn('docker compose down -v', script)


if __name__ == '__main__':
    unittest.main()
