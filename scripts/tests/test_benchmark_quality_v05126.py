"""V0.5.126 audit/document/cleanup contracts; stdlib-only and offline-safe."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/audit-benchmark-quality.py'
spec = importlib.util.spec_from_file_location('traffic_benchmark_quality_v05126', SCRIPT)
quality = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quality)


class BenchmarkQualityRegression(unittest.TestCase):
    def test_four_case_categories_keep_original_identity_and_intent(self):
        fixtures = (
            ('missed', {'time': 59.445, 'ground_truth_id': 42, 'direction': 'in',
                        'vehicle_type': 'bicycle', 'temporal_evidence': {'status': 'persisted_event_claimed_by_other_gt'}}),
            ('extra', {'time': 54.294, 'ai_event_id': 61, 'direction': 'out',
                       'vehicle_type': 'motorcycle', 'reason': 'spatial_duplicate_near_gt'}),
            ('direction', {'time': 58.9, 'ai_event_id': 60, 'ground_truth_id': 40,
                           'ground_truth_direction': 'out', 'ai_direction': 'in'}),
            ('class', {'time': 641.98, 'ai_event_id': 65, 'ground_truth_id': 45,
                       'ground_truth_vehicle_type': 'car', 'ai_vehicle_type': 'truck'}),
        )
        for kind, entry in fixtures:
            with self.subTest(kind=kind):
                issue = quality._issue(kind, entry)
                self.assertEqual(issue['kind'], kind)
                self.assertFalse(issue['identity_proven'])
                self.assertEqual(issue['ground_truth_id'], entry.get('ground_truth_id'))
                self.assertEqual(issue['ai_event_id'], entry.get('ai_event_id'))
                self.assertEqual(issue['timecode'].count(':'), 2)
        self.assertEqual(quality._issue('missed', fixtures[0][1])['audit_reason'], 'persisted_event_claimed_by_other_gt')

    def test_bad_timecodes_rejected(self):
        for val in (float('nan'), float('inf'), -1, True, '1.0'):
            with self.subTest(value=val):
                with self.assertRaises(ValueError):
                    quality._issue('extra', {'time': val})

    def test_invalid_images_and_symlinks_never_join(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'session_1_frame_24.jpg').write_bytes(b'x')
            (root/'unrelated.jpg').write_bytes(b'x')
            (root/'session_1_frame_bad.jpg').write_bytes(b'x')
            (root/'session_1_frame_25.jpg').symlink_to(root/'session_1_frame_24.jpg')
            self.assertEqual(quality._camera_index(root), [(24,'session_1_frame_24.jpg')])
            with self.assertRaises(ValueError):
                quality._camera_index(root/'missing')

    def test_no_excessive_or_invalid_review_window(self):
        for win in (0, 5.1, float('nan'), True):
            with self.subTest(window=win):
                with self.assertRaises(ValueError):
                    quality.analyze(Path('missing.zip'), window=win)

    def test_cleanup_only_removes_explicit_report_directories(self):
        text = (ROOT/'scripts/cleanup-generated.ps1').read_text('utf-8')
        self.assertIn('if ($Apply)', text)
        self.assertIn('if ($IncludeReleaseArtifacts)', text)
        self.assertIn('Preview only.', text)
        self.assertIn('ReparsePoint', text)
        for forbidden in ("'models'", "'videos'", "'snapshots'", "'datasets'", "'training-runs'",
                          "'gateway'", "'backend'", "'docs'", 'docker volume rm', 'docker compose down -v'):
            self.assertNotIn(forbidden, text)

    def test_single_root_readme_with_safety_categories_and_release_command(self):
        self.assertEqual(sorted(p.name for p in ROOT.glob('*.md')), ['README.md'])
        readme=(ROOT/'README.md').read_text('utf-8')
        for token in ('V0.5.126', 'Dataset', 'training-runs', 'dist-release', 'audit-benchmark-quality.ps1',
                      'cleanup-generated.ps1', '.\\scripts\\publish.ps1', '0.5.122'):
            self.assertIn(token, readme)
        script=(ROOT/'scripts/test.ps1').read_text('utf-8')
        self.assertIn('test_benchmark_quality_v05126.py', script)
        self.assertLess(script.index('test_benchmark_quality_v05126.py'),script.index('Invoke-Step "Frontend build"'))

if __name__ == '__main__':
    unittest.main()
