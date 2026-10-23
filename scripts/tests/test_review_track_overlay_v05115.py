"""V0.5.115 verified trace track overlays: stdlib-only tests."""
import gzip
import importlib.util
import json
import sys
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from unittest import mock

DIR=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('review_track_overlay_v05115',DIR/'annotate-benchmark-review-frames.py')
TOOL=importlib.util.module_from_spec(spec)
spec.loader.exec_module(TOOL)
GEO={'kind':'geometry_metadata','session_id':209,'frame_width':320,'frame_height':180,
     'line':[[.2,.5],[.8,.5]],'source_frame_width':320,'source_frame_height':180}


def frame(idx):
    return {'frame_index':idx,'gate_tracks':[
      {'track_id':14,'raw_track_id':107,'label':'motorcycle',
       'rect':[90.,45.,120.,98.],'final_gate_decision':'no-opposite-side-observation'},
      {'track_id':15,'raw_track_id':108,'label':'bicycle',
       'rect':[180.,20.,220.,110.],'final_gate_decision':'primary-accepted'}],
       'road_tracks':2,'road_margin_eligible_tracks':3,'near_gate_eligible_tracks':1}


class TrackOverlayTests(unittest.TestCase):
    def test_finite_segment_projection_and_sorted_track_labels(self):
        result=TOOL.bounded_track_annotations(frame(50),GEO)
        self.assertEqual({x['track_id'] for x in result},{14,15})
        self.assertEqual(result[-1]['decision'] if result[-1]['track_id']==15 else result[0]['decision'],
                         'primary-accepted')
        self.assertEqual(len(TOOL.bounded_track_annotations(frame(50),GEO,limit=1)),1)

    def test_invalid_boxes_fail_closed_not_zero_distance(self):
        row={'gate_tracks':[{'track_id':6,'rect':[0,float('nan'),1,2]},
                            {'track_id':7,'rect':['broken',0,10,20]},
                            {'track_id':8,'rect':[0,0,10,20]}]}
        self.assertEqual([x['track_id'] for x in TOOL.bounded_track_annotations(row,GEO)],[8])

    def test_manifest_binds_original_verified_sha_and_session(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d); (d/'missed_1').mkdir(); (d/'missed_1'/'frame_000051.jpg').write_bytes(b'jpg')
            evidence={'benchmark_id':82,'session_id':209,'source_trace_sha256':'verified'}
            case={'kind':'missed','case_id':1,'time_s':2.0,
                  'frames':[{'frame_index':51,'source_time_s':2.0,'file':'missed_1/frame_000051.jpg'}]}
            manifest={'format':'traffic-ai-review-frame-pack','schema_version':1,'benchmark_id':82,'session_id':209,
                      'verified_trace_sha256':'verified','scoring_modified':False,'source_fps':25,'source_frames':23650,
                      'cases':[case]}
            self.assertEqual(set(TOOL.validate_review_manifest(manifest,evidence,[case],d)),{51})
            for key,bad in [('session_id',208),('verified_trace_sha256','different'),('scoring_modified',True)]:
                tmp={**manifest,key:bad}
                with self.assertRaises(ValueError):TOOL.validate_review_manifest(tmp,evidence,[case],d)

    def test_symlink_escape_and_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);(d/'ok.jpg').write_bytes(b'jpg')
            for path in ('../secret.jpg','/etc/passwd','sub\\file.jpg','sub/missing.jpg'):
                with self.assertRaises(ValueError):TOOL._safe_jpeg(d,path)
            (d/'alias.jpg').symlink_to('/etc/passwd')
            with self.assertRaises(ValueError):TOOL._safe_jpeg(d,'alias.jpg')

    def test_streamed_selection_rejects_missing_or_duplicate_frames(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'b.zip'
            def mk(rows):
                payload='\n'.join(json.dumps(x) for x in [
                    {'kind':'session_metadata','session_id':209},GEO,*rows])+'\n'
                with zipfile.ZipFile(p,'w') as z:z.writestr('benchmark-trace.jsonl.gz',gzip.compress(payload.encode()))
            mk([frame(51),frame(56)])
            self.assertEqual(set(TOOL.verified_trace_frames(p,{51,56},209)[1]),{51,56})
            with self.assertRaisesRegex(ValueError,'missing'):
                TOOL.verified_trace_frames(p,{52},209)
            mk([frame(51),frame(51)])
            with self.assertRaisesRegex(ValueError,'Duplicate'):
                TOOL.verified_trace_frames(p,{51},209)

    def test_end_to_end_keeps_orig_jpeg_and_writes_one_upload_zip(self):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td);review=d/'review';review.mkdir(); folder=review/'missed_1';folder.mkdir()
            src=folder/'frame_000051.jpg';src.write_bytes(b'original-jpeg')
            case={'kind':'missed','case_id':1,'time_s':2.0,'direction':'in','vehicle_type':'motorcycle',
                'frames':[{'frame_index':51,'source_time_s':2.0,'file':'missed_1/frame_000051.jpg'}]}
            evidence={'benchmark_id':82,'session_id':209,'source_trace_sha256':'verified'}
            manifest={'format':'traffic-ai-review-frame-pack','schema_version':1,'benchmark_id':82,'session_id':209,
                'source_fps':25,'source_frames':23650,'verified_trace_sha256':'verified',
                'scoring_modified':False,'cases':[case]}
            (review/'review-manifest.json').write_text(json.dumps(manifest))
            fakecv2=types.SimpleNamespace(
                FONT_HERSHEY_SIMPLEX=1,IMWRITE_JPEG_QUALITY=90,
                imread=lambda path:types.SimpleNamespace(shape=(180,320,3)),
                imwrite=lambda path,image,settings: (Path(path).write_bytes(b'annotated-jpeg') or True),
                rectangle=lambda *a:None,line=lambda *a:None,putText=lambda *a:None)
            with mock.patch.object(TOOL,'_review_tool',return_value=types.SimpleNamespace(verified_cases=lambda p:(evidence,{},[case]))),\
                 mock.patch.object(TOOL,'verified_trace_frames',return_value=(GEO,{51:frame(51)})),\
                 mock.patch.dict(sys.modules,{'cv2':fakecv2}):
                result=TOOL.annotate(d/'benchmark.zip',review,d/'out',expected_session=209)
            self.assertEqual(result['image_count'],1)
            self.assertEqual(src.read_bytes(),b'original-jpeg')
            with zipfile.ZipFile(result['bundle']) as z:
                self.assertEqual(z.testzip(),None)
                self.assertIn('missed_1/frame_000051.jpg',z.namelist())
                self.assertNotIn('review-tracks-upload.zip',z.namelist())
            content=json.loads((d/'out'/'trace-overlay.json').read_text())
            self.assertFalse(content['labels_are_ground_truth'])
            self.assertFalse(content['scoring_modified'])
            self.assertEqual(content['frames'][0]['trace_tracks'][0]['track_id'] in [14,15],True)
            with self.assertRaisesRegex(ValueError,'not empty'):
                with mock.patch.object(TOOL,'_review_tool',return_value=types.SimpleNamespace(verified_cases=lambda p:(evidence,{},[case]))):
                    TOOL.annotate(d/'benchmark.zip',review,d/'out')

    def test_shell_mounts_all_verifiers_read_only_and_no_original_write(self):
        ps=(DIR/'annotate-benchmark-review-frames.ps1').read_text(encoding='utf-8')
        self.assertIn('benchmark-forensics.py:ro',ps)
        self.assertIn('benchmark-gate.py:ro',ps)
        self.assertIn('export-benchmark-review-frames.py:ro',ps)
        self.assertIn('review-original:ro',ps)
        self.assertIn('ai-service',ps)
        self.assertNotIn('pip install',ps)

    def test_output_cannot_be_original_subfolder(self):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td)
            with self.assertRaisesRegex(ValueError,'separate'):
                TOOL.annotate(d/'archive.zip',d/'frames',d/'frames'/'child')

if __name__=='__main__':unittest.main()
