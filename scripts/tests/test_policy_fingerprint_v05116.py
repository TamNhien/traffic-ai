"""A deployed policy change must alter its recorded runtime fingerprint."""
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class PolicyFingerprintTests(unittest.TestCase):
    def test_classification_and_tracking_changes_alter_source_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            app = Path(folder) / 'app'
            app.mkdir()
            for source in (ROOT / 'ai-service/app').glob('*.py'):
                shutil.copyfile(source, app / source.name)
            spec = importlib.util.spec_from_file_location('isolated_identity_v116', app / 'trace_identity.py')
            identity = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(identity)
            original = identity.source_fingerprint()
            self.assertEqual(original, identity.source_fingerprint())
            for name in ('classification.py', 'tracking.py'):
                with self.subTest(policy=name):
                    path = app / name
                    content = path.read_bytes()
                    path.write_bytes(content + b'\n# changed policy bytes\n')
                    self.assertNotEqual(original, identity.source_fingerprint())
                    path.write_bytes(content)
                    self.assertEqual(original, identity.source_fingerprint())


if __name__ == '__main__':
    unittest.main()
