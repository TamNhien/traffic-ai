"""Session-scoped frame evidence is only navigation data; do not count or relabel."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT/'scripts/audit-benchmark-frame-evidence.py'
spec = importlib.util.spec_from_file_location('verified_camera_evidence_132', SRC)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class CameraEvidenceRegression(unittest.TestCase):
    def put_image(self,p):
        p.write_bytes(b'\xff\xd8\xff'+b'Camera JPEG test bytes')

    def test_session_isolation_prevents_cross_run_frame_collision(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            self.put_image(root/'session_250_frame_1486.jpg')
            self.put_image(root/'session_251_frame_1486.jpg')
            self.put_image(root/'session_251_frame_1487.jpg')
            files=mod.camera_index(root,251)
            self.assertEqual(sorted(files),[1486,1487])
            self.assertTrue(all('251' in f.name for f in files.values()))
            self.assertEqual(list(mod.camera_index(root,250)),[1486])
            with self.assertRaisesRegex(ValueError,'No JPEG for Session'):
                mod.camera_index(root,252)

    def test_rejects_duplicates_symlinks_non_jpegs_and_bad_signatures(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            self.put_image(root/'session_251_frame_10.jpg')
            (root/'session_251_frame_10.jpeg').write_bytes(b'\xff\xd8\xffTEST')
            with self.assertRaisesRegex(ValueError,'Multiple JPEG'):
                mod.camera_index(root,251)
            (root/'session_251_frame_10.jpeg').unlink()
            (root/'session_251_frame_11.jpg').symlink_to(root/'session_251_frame_10.jpg')
            (root/'session_251_frame_12.jpg').write_bytes(b'notreallyjpg')
            with self.assertRaisesRegex(ValueError,'JPEG signature'):
                mod.camera_index(root,251)
            (root/'session_251_frame_12.jpg').unlink()
            self.assertEqual(list(mod.camera_index(root,251)),[10])

    def test_gap_not_nearby_does_not_copy_false_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);camera=root/'camera';camera.mkdir()
            self.put_image(camera/'session_251_frame_1486.jpg')
            report={'benchmark':{'id':91,'source_fps':25},'session_id':251,'missed':1,'missed_items':[{'time':591.091,'ground_truth_id':2,'vehicle_type':'bicycle','direction':'in'}],
                'false_positives':1,'false_positive_items':[{'time':59.446,'ai_event_id':3,'direction':'out','vehicle_type':'motorcycle'}],
                'direction_mismatches':0,'direction_mismatch_items':[],'class_mismatches':0,'class_mismatch_items':[]}
            with patch.object(mod.compare,'_read_evidence',return_value={'report':report}):
                result=mod.analyze(Path('fake.zip'),camera)
            self.assertEqual(result['summary'],{'issues':2,'nearby_snapshots':1,'insufficient_coverage':1})
            self.assertTrue(all(c['camera_session_verified'] for c in result['issues']))
            self.assertTrue(all(c['identity_proven'] is False for c in result['issues']))
            out=root/'output';mod.write_outputs(result,camera,out)
            self.assertEqual(len(list((out/'evidence').glob('*.jpg'))),1)
            result2=json.loads((out/'camera-review.json').read_text('utf-8'))
            missing=next(c for c in result2['issues'] if c['kind']=='missed')
            self.assertEqual(missing['camera_status'],'insufficient_frame_coverage')
            self.assertIsNone(missing['evidence_file'])
            with self.assertRaisesRegex(ValueError,'empty or new'):
                mod.write_outputs(result,camera,out)

    def test_no_source_folder_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td); result={'issues':[], 'summary':{'issues':0,'nearby_snapshots':0,'insufficient_coverage':0},'benchmark_id':91,'session_id':251,'warnings':[]}
            with self.assertRaisesRegex(ValueError,'Output cannot'):
                mod.write_outputs(result,folder,folder/'nested')

    def test_invalid_gap_rejected_before_touching_file(self):
        for gap in [-1,0,2.1,True,float('nan')]:
            with self.subTest(gap=gap):
                with self.assertRaises(ValueError):mod.analyze(Path('/no/zip'),Path('/no/images'),gap)

    def test_release_contract_and_local_only(self):
        text=SRC.read_text('utf-8')
        for forbidden in ('rclone','gdrive:','docker volume rm','docker compose down -v','UPDATE system_settings','INSERT INTO ground_truth'):
            self.assertNotIn(forbidden,text)
        ps=(ROOT/'scripts/audit-benchmark-frame-evidence.ps1').read_text('utf-8')
        self.assertIn('/src:ro',ps)
        self.assertIn('/camera:ro',ps)
        self.assertIn('python:3.14.10-slim',ps)
        test=(ROOT/'scripts/test.ps1').read_text('utf-8')
        self.assertIn('test_camera_evidence_v05132.py',test)
        self.assertLess(test.index('test_camera_evidence_v05132.py'),test.index('Invoke-Step "Frontend build"'))
        self.assertGreaterEqual(int((ROOT/'VERSION').read_text().strip().split('.')[-1]), 132)
        self.assertEqual(sorted(p.name for p in ROOT.glob('*.md')),['README.md'])

if __name__=='__main__':unittest.main()
