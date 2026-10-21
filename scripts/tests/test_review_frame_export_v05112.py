"""V0.5.112 verified source-video review frame export regression (stdlib only)."""
import gzip
import importlib.util
import json
import math
import sys
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('review_frame_export_v05112', HERE/'export-benchmark-review-frames.py')
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)

class FakeCapture:
    def __init__(self, video, *, fps=25., count=125, width=320, height=180):
        self.metrics={1:fps,2:count,3:width,4:height}
        self.pos=0
        self.closed=False
    def isOpened(self):return True
    def get(self,k):return self.metrics[k]
    def set(self,k,value):self.pos=int(value);return True
    def read(self):return True,object()
    def release(self):self.closed=True

class ExportFrameTests(unittest.TestCase):
    def test_indices_preserve_frame_clock_and_clip_bounds(self):
        self.assertEqual(TOOL.review_indices(0,25,125),[0,5,10])
        self.assertEqual(TOOL.review_indices(4.96,25,125),[114,119,124])

    def test_invalid_clocks_and_unbounded_scans_rejected(self):
        for args in ((math.nan,25,125),(4,0,125),(4,25,0)):
            with self.assertRaises(ValueError): TOOL.review_indices(*args)
        with self.assertRaises(ValueError): TOOL.review_indices(4,25,125,half_window=3)
        with self.assertRaises(ValueError): TOOL.review_indices(4,25,125,step=.001)

    def test_video_metadata_rejects_lookalike_wrong_fps_duration_and_aspect(self):
        base=dict(actual_fps=25.,actual_count=125,actual_width=320,actual_height=180,
                  expected_fps=25.,expected_count=125,trace_width=320,trace_height=180)
        TOOL.verify_video_metrics(**base)
        for change in ({'actual_fps':24}, {'actual_count':130}, {'actual_width':240}, {'trace_height':0}):
            with self.assertRaises(ValueError): TOOL.verify_video_metrics(**(base|change))

    def test_script_does_not_generate_training_labels_or_gt_mutations(self):
        source=(HERE/'export-benchmark-review-frames.py').read_text(encoding='utf-8')
        self.assertIn("'label_status':'UNREVIEWED", source)
        self.assertIn("'scoring_modified':False", source)
        self.assertNotIn('yolo_train(',source)

    def test_end_to_end_fake_cv2_exports_report_not_labels(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d)
            archive=d/'b.zip';video=d/'original.mp4';video.write_bytes(b'synthetic-video-handle')
            with zipfile.ZipFile(archive,'w') as z:
                data=(json.dumps({'kind':'session_metadata','session_id':9,'source_fps':25.,'source_frame_count':125})+'\n'+
                      json.dumps({'kind':'geometry_metadata','session_id':9,
                                  'source_frame_width':320,'source_frame_height':180})+'\n').encode()
                z.writestr('benchmark-trace.jsonl.gz',gzip.compress(data))
            evidence=dict(benchmark_id=13,session_id=9,source_trace_sha256='abc')
            config={'benchmark_snapshot':{'geometry':{'line_x1':.2,'line_y1':.5,'line_x2':.8,'line_y2':.5}}}
            cases=[{'kind':'missed','case_id':11,'time_s':2.0,'direction':'in','vehicle_type':'bicycle'},
                   {'kind':'extra','case_id':22,'time_s':3.0,'direction':'out','vehicle_type':'motorcycle'}]
            fake_cv2=types.SimpleNamespace(CAP_PROP_FPS=1,CAP_PROP_FRAME_COUNT=2,CAP_PROP_FRAME_WIDTH=3,
                CAP_PROP_FRAME_HEIGHT=4,CAP_PROP_POS_FRAMES=5,FONT_HERSHEY_SIMPLEX=6,
                IMWRITE_JPEG_QUALITY=7,VideoCapture=lambda path: FakeCapture(path),line=lambda *a:None,
                putText=lambda *a:None,resize=lambda frame,shape:frame,
                imwrite=lambda path,frame,params: (Path(path).write_bytes(b'fake-jpg') or True))
            with mock.patch.object(TOOL,'verified_cases',return_value=(evidence,config,cases)),\
                 mock.patch.dict(sys.modules,{'cv2':fake_cv2}):
                report=TOOL.export_frames(archive,video,d/'out',expected_session=9)
            self.assertEqual(len(report['cases']),2)
            self.assertEqual(sum(len(r['frames']) for r in report['cases']),10)
            self.assertFalse(report['scoring_modified'])
            self.assertEqual(len(list((d/'out').rglob('*.jpg'))),10)
            self.assertFalse(list((d/'out').rglob('*.txt')))
            self.assertEqual(json.loads((d/'out'/'review-manifest.json').read_text())['session_id'],9)

    def test_wrong_session_fails_before_creating_output(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);v=d/'video.mp4';v.write_bytes(b'video')
            with mock.patch.object(TOOL,'verified_cases',return_value=(dict(session_id=9),{},[])):
                with self.assertRaisesRegex(ValueError,'Expected session'):
                    TOOL.export_frames(d/'b.zip',v,d/'out',expected_session=10)
            self.assertFalse((d/'out').exists())

    def test_poweshell_runs_bundled_ai_image_not_host_cv2(self):
        shell=(HERE/'export-benchmark-review-frames.ps1').read_text(encoding='utf-8')
        self.assertIn("'--entrypoint','python','ai-service'",shell)
        self.assertIn('benchmark-forensics.py',shell)
        self.assertNotIn('pip install',shell)

if __name__=='__main__':unittest.main()
