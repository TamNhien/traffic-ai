"""Offline release regression for V0.5.75 replay audit (stdlib only)."""
from __future__ import annotations

import gzip
import hashlib
import zipfile
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'replay-diff.py'
spec = importlib.util.spec_from_file_location('traffic_replay_diff', SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def make_trace(path, session=1, events=None, *, frames=4, fps=25.0, complete=True, geom=None):
    if events is None:
        events = []
    geometry = geom or {
        'line': [[0.3, 0.4], [0.7, 0.6]],
        'road_zone': [[0, 0], [1, 0], [1, 1], [0, 1]],
        'frame_width': 1440, 'frame_height': 811,
        'source_frame_width': 2960, 'source_frame_height': 1668,
        'coordinate_system': 'normalized_processed_frame',
    }
    rows = [
        {'kind':'session_metadata','camera_id':1,'session_id':session,'source_frame_count':frames,'source_fps':fps},
        {'kind':'geometry_metadata','camera_id':1,'session_id':session,**geometry},
    ] + [{'camera_id':1,'session_id':session,'frame_index':i,'source_time_seconds': (i-1)/fps} for i in range(1,frames+1)]
    for i, event in enumerate(events):
        rows.append({'kind':'event_delivery','camera_id':1,'session_id':session,
                     'stage':'backend_acknowledged','outcome':event.get('outcome','created'),
                     'tracking_id':event.get('tracking_id',i),'vehicle_type':event.get('vehicle_type','motorcycle'),
                     'direction':event.get('direction','in'),'crossing_method':event.get('crossing_method','direct'),
                     'source_frame_index':event.get('source_frame_index',2),
                     'source_time_seconds':event.get('source_time_seconds',0.04),
                     'crossing_x':event.get('crossing_x',0.5),
                     'crossing_y':event.get('crossing_y',0.5),
                     'dedup_reason':event.get('dedup_reason')})
    if complete:
        rows.append({'kind':'delivery_summary','camera_id':1,'session_id':session,
                     'delivery_drain_complete':True,'delivery_audit_dropped':0,'pending_events':0})
    data = ''.join(json.dumps(row)+'\n' for row in rows).encode()
    if str(path).endswith('.gz'):
        with gzip.open(path,'wb') as stream:stream.write(data)
    else:path.write_bytes(data)


class ReplayAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def paths(self):
        return self.folder/'before.jsonl', self.folder/'after.jsonl'

    def test_equal_crossings_ignore_unstable_tracker_and_db_ids(self):
        a,b=self.paths()
        make_trace(a, events=[{'tracking_id':10}])
        make_trace(b,session=2,events=[{'tracking_id':5000}])
        report=module.summarize(module.load_trace(a),module.load_trace(b))
        self.assertEqual(report['summary']['created_pairs'],1)
        self.assertEqual(report['summary']['created_removed'],0)
        self.assertEqual(report['summary']['created_introduced'],0)
        self.assertEqual(report['summary']['decision_changes'],0)

    def test_decision_flip_is_reported_without_guessing_ground_truth(self):
        a,b=self.paths()
        make_trace(a,events=[{'outcome':'deduplicated','dedup_reason':'same-track-repeat-jitter'}])
        make_trace(b,session=2,events=[{}])
        report=module.summarize(module.load_trace(a),module.load_trace(b))
        self.assertEqual(report['summary']['decision_changes'],1)
        self.assertEqual(report['summary']['created_introduced'],1)
        self.assertIn('not-ground-truth',report['analysis_type'])

    def test_removed_and_introduced_event(self):
        a,b=self.paths()
        make_trace(a,events=[{'direction':'out','crossing_x':0.4}])
        make_trace(b,session=2,events=[{'direction':'in','crossing_x':0.6}])
        stats=module.summarize(module.load_trace(a),module.load_trace(b))['summary']
        self.assertEqual((stats['created_removed'],stats['created_introduced']), (1,1))

    def test_finite_windows_reject_nonmatching_and_pair_small_jitter(self):
        a,b=self.paths()
        make_trace(a,events=[{'crossing_x':0.5,'source_time_seconds':0.04}])
        make_trace(b,session=2,events=[{'crossing_x':0.509,'source_time_seconds':0.06}])
        report=module.summarize(module.load_trace(a),module.load_trace(b))
        self.assertEqual(report['summary']['created_pairs'],1)
        self.assertEqual(report['summary']['created_total_delta'],0)
        self.assertEqual(module.summarize(module.load_trace(a),module.load_trace(b),distance_window=0.005)['summary']['created_pairs'],0)

    def test_degenerate_reused_trace_rejected(self):
        a,b=self.paths()
        make_trace(a)
        make_trace(b,session=1)
        with self.assertRaisesRegex(module.EvidenceError,'same session'):
            module.summarize(module.load_trace(a),module.load_trace(b))

    def test_different_geometry_rejected_even_matching_stats(self):
        a,b=self.paths()
        make_trace(a)
        make_trace(b,session=2,geom={'line':[[0,0],[1,1]],'road_zone':[[0,0],[1,0],[1,1]]})
        with self.assertRaisesRegex(module.EvidenceError,'geometry differs'):
            module.summarize(module.load_trace(a),module.load_trace(b))

    def test_incomplete_missing_footer_rejected(self):
        a,b=self.paths()
        make_trace(a,complete=False)
        with self.assertRaisesRegex(module.EvidenceError,'incomplete'):
            module.load_trace(a)

    def test_incomplete_frame_stream_rejected(self):
        a,b=self.paths()
        make_trace(a,frames=4)
        data=a.read_text().splitlines()
        data=[x for x in data if '"frame_index": 3,' not in x]
        a.write_text('\n'.join(data)+'\n')
        with self.assertRaisesRegex(module.EvidenceError,'Missing or duplicate frame'):
            module.load_trace(a)

    def test_gzip_and_plain_give_equal_reports(self):
        a,b=self.paths()
        make_trace(a,events=[{}])
        b=self.folder/'after.jsonl.gz'
        make_trace(b,session=2,events=[{}])
        self.assertEqual(module.summarize(module.load_trace(a),module.load_trace(b))['summary']['created_pairs'],1)

    def test_nan_out_of_range_or_bad_ack_rejected(self):
        a,b=self.paths()
        for bad in (float('nan'), -1, 1.5):
            make_trace(a,events=[{'crossing_x':bad}])
            with self.assertRaises(module.EvidenceError):module.load_trace(a)
        make_trace(a,events=[{}])
        data=a.read_text().replace('"stage": "backend_acknowledged"','"stage": "queued"')
        a.write_text(data)
        with self.assertRaisesRegex(module.EvidenceError,'acknowledgement'):
            module.load_trace(a)

    def test_cli_strict_fails_replay_change_but_generates_reports(self):
        a,b=self.paths()
        make_trace(a,events=[{}])
        make_trace(b,session=2,events=[{}, {'crossing_x':0.7}])
        folder=self.folder/'out'
        code=module.main(['--previous',str(a),'--current',str(b),'--output-dir',str(folder),'--strict'])
        self.assertEqual(code,1)
        self.assertTrue((folder/'replay-diff.json').exists())
        self.assertIn('## Sự kiện', (folder/'replay-diff.md').read_text(encoding='utf8'))

    def test_cli_rejects_bad_evidence_without_emitting_fake_report(self):
        a,b=self.paths()
        make_trace(a,complete=False)
        make_trace(b,session=2)
        folder=self.folder/'out'
        self.assertEqual(module.main(['--previous',str(a),'--current',str(b),'--output-dir',str(folder)]),2)
        self.assertFalse(folder.exists())

    def test_benchmark_zip_embedded_gzip_trace_verified(self):
        a, b = self.paths()
        make_trace(a, events=[{}])
        make_trace(b, session=2, events=[{}])
        exports = []
        for raw in (a, b):
            filename = 'benchmark-trace.jsonl.gz'
            content = gzip.compress(raw.read_bytes())
            manifest = {
                'format':'traffic-ai-benchmark-diagnostics','schema_version':1,
                'files':{filename:{'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()}},
            }
            dest = self.folder / f'{raw.stem}.zip'
            with zipfile.ZipFile(dest, 'w') as z:
                z.writestr(filename,content)
                z.writestr('manifest.json',json.dumps(manifest))
            exports.append(dest)
        report = module.summarize(module.load_trace(exports[0]),module.load_trace(exports[1]))
        self.assertEqual(report['summary']['created_pairs'],1)
        with zipfile.ZipFile(exports[1],'a') as z:
            # Tamper manifest, keeping member bytes intact.
            z.writestr('fake-extra.json','{}')
        # Additional well-formed entries are allowed; tampering with trace is not.
        self.assertEqual(module.load_trace(exports[1]).session_id,2)
        bad = self.folder/'bad.zip'
        with zipfile.ZipFile(bad,'w') as z:
            z.writestr('benchmark-trace.jsonl.gz',gzip.compress(b.read_bytes()))
            z.writestr('manifest.json',json.dumps({'format':'traffic-ai-benchmark-diagnostics',
              'schema_version':1,'files':{'benchmark-trace.jsonl.gz':{'bytes':3,'sha256':'0'*64}}}))
        with self.assertRaisesRegex(module.EvidenceError,'size mismatch'):
            module.load_trace(bad)

    def test_missing_trace_in_benchmark_zip_fails_closed(self):
        zip_path = self.folder/'no-trace.zip'
        with zipfile.ZipFile(zip_path,'w') as z:
            z.writestr('manifest.json',json.dumps({'format':'traffic-ai-benchmark-diagnostics',
              'schema_version':1, 'files':{}}))
        with self.assertRaisesRegex(module.EvidenceError,'must include one benchmark trace'):
            module.load_trace(zip_path)

    def test_hungarian_finds_optimal_over_naive_greedy(self):
        # First row can match both columns, second can match only first;
        # max-cardinality matching must keep both rather than choose greedy.
        a1=module.Crossing(2,.08,.50,.50,'in','motorcycle','direct',1,'created','')
        a2=module.Crossing(2,.00,.49,.50,'in','motorcycle','direct',2,'created','')
        b1=module.Crossing(2,.05,.495,.50,'in','motorcycle','direct',3,'created','')
        b2=module.Crossing(2,.10,.53,.50,'in','motorcycle','direct',4,'created','')
        pairs,left,right=module.pair_crossings([a1,a2],[b1,b2],.12,.04)
        self.assertEqual((len(pairs),len(left),len(right)),(2,0,0))


if __name__=='__main__': unittest.main()
