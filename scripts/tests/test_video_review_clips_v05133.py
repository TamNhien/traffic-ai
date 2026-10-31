"""V0.5.133 video snippets are review-only and fail closed on wrong video/session."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT/'scripts/export-benchmark-review-clips.py'
spec = importlib.util.spec_from_file_location('clip_review_133',SCRIPT)
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


def sample():
    return {'session_id':252,'benchmark_id':92,'fps':25.0,'duration':8.0,'frames':200,
            'width':640,'height':360,'source_basename':'clip1.mp4','archive_sha256':'ab'*32,
            'cases':[{'time':1.0,'kind':'missed','review_id':'REVIEW-01'},
                     {'time':1.4,'kind':'direction','review_id':'REVIEW-02'},
                     {'time':6.0,'kind':'extra','review_id':'REVIEW-03'}]}

class VideoReviewRegression(unittest.TestCase):
    def test_window_merging_preserves_separate_case_references(self):
        records=review.groups(sample()['cases'],8.,1.0)
        self.assertEqual(len(records),2)
        self.assertEqual(records[0]['case_ids'],['REVIEW-01','REVIEW-02'])
        self.assertEqual(records[0]['start'],0.)
        self.assertEqual(records[0]['end'],2.4)
        self.assertEqual(records[1]['case_ids'],['REVIEW-03'])

    def test_mismatched_video_or_wrong_filename_rejected(self):
        expected=sample();ok={'fps':25.,'duration':8.,'width':640,'height':360,'frames':200}
        review.verify_video(expected,ok,Path('clip1.mp4'))
        for bad in [dict(ok,fps=30.),dict(ok,duration=10.),dict(ok,width=800),dict(ok,frames=230)]:
            with self.assertRaisesRegex(ValueError,'Video'):
                review.verify_video(expected,bad,Path('clip1.mp4'))
        with self.assertRaisesRegex(ValueError,'filename'):
            review.verify_video(expected,ok,Path('unrelated.mp4'))

    def test_invalid_windows_and_timecodes_rejected(self):
        for value in (-.1,0.,4.01,float('nan'),True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    review.render(Path('/missing.zip'),Path('/missing.mp4'),Path('/out'),half_window=value)
        with self.assertRaises(ValueError):
            review.groups([{'time':9.0,'review_id':'x'}],8.,.1)

    def test_render_writes_checksums_and_finishes_manifest_last(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); zipfile=root/'input.zip'; zipfile.write_bytes(b'Fake benchmark')
            video=root/'clip1.mp4';video.write_bytes(b'0123456789'*24)
            destination=root/'output';commands=[];written={}
            def runner(cmd,**kwargs):
                commands.append(cmd)
                if cmd[0]=='ffprobe':
                    length = written.get(str(cmd[-1]),8.0)
                    return subprocess.CompletedProcess(cmd,0,stdout=json.dumps({
                        'streams':[{'width':640,'height':360,'avg_frame_rate':'25/1','nb_frames':str(round(length*25))}],
                        'format':{'duration':str(length)}}))
                written[str(cmd[-1])] = float(cmd[cmd.index('-t')+1])
                Path(cmd[-1]).write_bytes(b'fake MP4 segment output'*20)
                return subprocess.CompletedProcess(cmd,0,stdout='')
            with patch.object(review,'read_cases',return_value=sample()):
                out=review.render(zipfile,video,destination,expected_session=252,half_window=1.0,runner=runner)
            self.assertEqual(len(out['cases']),3)
            self.assertEqual(len(out['clips']),2)
            self.assertFalse(out['counts_or_ground_truth_modified'])
            self.assertFalse(out['camera_source_identity_proven'])
            self.assertEqual(len(list(destination.glob('*.mp4'))),2)
            self.assertEqual(len(out['video_sha256']),64)
            self.assertTrue((destination/'review-clips.json').exists())
            self.assertFalse(any(x.name.startswith('.review-pending') for x in destination.iterdir()))
            self.assertEqual(len([c for c in commands if c[0] == 'ffmpeg']), 2)
            self.assertTrue(all('-an' in c for c in commands if c[0] == 'ffmpeg'))
            with patch.object(review,'read_cases',return_value=sample()):
                with self.assertRaisesRegex(ValueError,'empty'):
                    review.render(zipfile,video,destination,runner=runner)

    def test_render_failure_does_not_publish_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); archive=root/'b.zip';archive.write_bytes(b'dummy ZIP')
            video=root/'clip1.mp4';video.write_bytes(b'0'*220)
            def runner(cmd,**kwargs):
                if cmd[0]=='ffprobe':
                    return subprocess.CompletedProcess(cmd,0,stdout=json.dumps({
                        'streams':[{'width':640,'height':360,'avg_frame_rate':'25/1','nb_frames':'200'}],
                        'format':{'duration':'8'}}))
                raise subprocess.CalledProcessError(1,cmd)
            output=root/'evidence'
            with patch.object(review,'read_cases',return_value=sample()):
                with self.assertRaises(subprocess.CalledProcessError):
                    review.render(archive,video,output,runner=runner)
            self.assertFalse((output/'review-clips.json').exists())
            self.assertEqual(list(output.iterdir()),[])

    def test_source_verifier_and_shell_guards(self):
        text=SCRIPT.read_text(encoding='utf-8')
        ps=(ROOT/'scripts/export-benchmark-review-clips.ps1').read_text(encoding='utf-8')
        self.assertIn('compare._read_evidence(archive)',text)
        self.assertIn('sha256(video)',text)
        self.assertIn("'camera_source_identity_proven':False",text)
        self.assertIn("'counts_or_ground_truth_modified':False",text)
        for forbidden in ('rclone','gdrive:','docker volume rm','DROP TABLE','DELETE FROM ground_truth'):
            self.assertNotIn(forbidden,text+ps)
        self.assertIn("'--network','none'",ps)
        self.assertIn('--read-only',ps)
        self.assertIn(':ro',ps)
        self.assertIn('traffic-ai-ai-service:latest',ps)
        self.assertIn('test_video_review_clips_v05133.py',(ROOT/'scripts/test.ps1').read_text('utf-8'))
        self.assertEqual((ROOT/'VERSION').read_text().strip(),'0.5.133')
        self.assertEqual(sorted(f.name for f in ROOT.glob('*.md')),['README.md'])

if __name__=='__main__':unittest.main()
