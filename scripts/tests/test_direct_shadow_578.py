"""Evidence-free dedup decisions and offline GT scoring regressions."""
from __future__ import annotations
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
spec = spec_from_file_location('shadow_counterfactual', ROOT/'scripts/evaluate-direct-shadow.py')
mod = module_from_spec(spec)
spec.loader.exec_module(mod)


def event(i, t, x, *, direction='out', category='motorcycle', tid=None, mode='direct'):
    return {'id':i,'source_time_seconds':t,'source_frame_index':int(25*t),
            'crossing_x':x,'crossing_y':.42,'direction':direction,'vehicle_type':category,
            'tracking_id':tid or i,'crossing_method':mode}


def zipped_fixture(path, *, malicious=False):
    marks=[{'id':1,'source_time_seconds':5.0,'direction':'out','vehicle_type':'motorcycle'}]
    events=[event(11,5.0,.59),event(12,5.28,.598587)]
    report=mod.match_crossings(marks,events,.75)
    report['session_id']=20
    session={'id':20,'status':'completed'}
    items={'ground-truth.json':marks,'events.json':events,'report.json':report,'session.json':session}
    raw={k:json.dumps(v).encode() for k,v in items.items()}
    manifest={'format':'traffic-ai-benchmark-diagnostics','session_id':20,
             'files':{name:{'bytes':len(v),'sha256':sha256(v).hexdigest()} for name,v in raw.items()}}
    if malicious:
        manifest['files']['events.json']['sha256']='bad'
    with ZipFile(path,'w') as z:
        for name,content in raw.items():z.writestr(name,content)
        z.writestr('manifest.json',json.dumps(manifest))


class DirectShadowOfflineTests(unittest.TestCase):
    def test_overlapping_same_motorcycle_track_ids_are_collapsed(self):
        keep,removed=mod.dedup_counterfactual([event(11,5.,.59),event(12,5.28,.598587)])
        self.assertEqual([v['id'] for v in keep],[11])
        self.assertEqual(removed[0]['removed_event_id'],12)

    def test_nearby_real_vehicle_different_location_is_kept(self):
        keep,removed=mod.dedup_counterfactual([event(11,5.,.59),event(12,5.28,.62)])
        self.assertEqual(len(keep),2)
        self.assertFalse(removed)

    def test_opposite_direction_or_category_is_kept(self):
        keep,removed=mod.dedup_counterfactual([event(11,5.,.59),
            event(12,5.28,.598,direction='in'),
            event(13,5.28,.598,category='bicycle')])
        self.assertEqual(len(keep),3)
        self.assertFalse(removed)

    def test_rescue_or_late_crossing_is_kept(self):
        keep,removed=mod.dedup_counterfactual([event(11,5.,.59),
            event(12,5.28,.598,mode='rescued'),event(13,5.60,.598)])
        self.assertEqual(len(keep),3)
        self.assertFalse(removed)

    def test_verified_benchmark_what_if(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'mock.zip';zipped_fixture(p)
            result=mod.analyze(p)
            self.assertEqual(result['baseline']['ai_total'],2)
            self.assertEqual(result['counterfactual']['ai_total'],1)
            self.assertEqual(result['counterfactual']['matched'],1)
            self.assertEqual(result['counterfactual']['false_positives'],0)
            self.assertEqual(result['baseline']['false_positives'],1)

    def test_bad_checksum_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'mock.zip';zipped_fixture(p,malicious=True)
            with self.assertRaises(mod.InvalidBenchmark):mod.analyze(p)

    def test_crossing_missing_coordinates_not_suppressed(self):
        a=event(11,5.,.59);b=event(12,5.28,.598); b['crossing_x']=None
        keep,removed=mod.dedup_counterfactual([a,b])
        self.assertEqual(len(keep),2)
        self.assertFalse(removed)


if __name__ == '__main__':unittest.main()
