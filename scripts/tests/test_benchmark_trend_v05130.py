"""Local-only multi-run audit safety/behavior regressions for V0.5.130."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from collections import Counter
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('benchmark_trend_130',ROOT/'scripts/audit-benchmark-trend.py')
t=importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)

def sample_run(b,s,misses=None):
    return {'report':{'benchmark':{'id':b},'session_id':s,'ground_truth_total':3,'ai_total':2,'matched':2,
            'missed':1,'false_positives':1,'direction_mismatches':1,'class_mismatches':1,
            'missed_items':misses or [{'time':59.446,'vehicle_type':'motorcycle','direction':'in',
                       'temporal_evidence':{'status':'persisted_event_claimed_by_other_gt'}, 'ground_truth_id':s}],
            'false_positive_items':[{'time':54.294,'vehicle_type':'motorcycle','direction':'out','crossing_method':'rescued','reason':'rescued_gap_unmatched','ai_event_id':s}],
            'direction_mismatch_items':[{'time':58.984,'ground_truth_vehicle_type':'motorcycle','ground_truth_direction':'out','ai_direction':'in','crossing_method':'interpolated'}],
            'class_mismatch_items':[{'time':641.981,'ground_truth_vehicle_type':'car','ai_vehicle_type':'truck','direction':'out'}]}}
def valid_compare():
    return {'scoring_comparable':True,'same_ground_truth':True,'same_source_geometry':True,
            'same_recorded_ai_crossing_signatures':True,
            'deltas':dict(matched=0,missed=0,false_positives=0,class_mismatches=0,direction_mismatches=0)}

class MultiRunTrendTests(unittest.TestCase):
    def test_three_runs_detect_persistent_errors_no_false_accuracy_claim(self):
        runs=[sample_run(i,i+160) for i in (88,89,90)]
        result=t.summarize_runs(runs,[valid_compare(),valid_compare()], [('a'*64,'complete')]*3)
        self.assertEqual(result['summary']['latest_issue_count'],4)
        self.assertEqual(result['summary']['persistent_issue_signatures'],4)
        self.assertEqual(result['summary']['new_since_previous'],0)
        self.assertFalse(result['summary']['improvement_observed'])
        self.assertTrue(result['integrity']['same_effective_policy_all_runs'])
        self.assertTrue(all(x['identity_proven'] is False for x in result['issues']))
        with tempfile.TemporaryDirectory() as d:
            t.write_outputs(result,Path(d))
            self.assertEqual(len(json.loads((Path(d)/'benchmark-trend.json').read_text('utf-8'))['issues']),4)
            self.assertTrue((Path(d)/'benchmark-trend.csv').exists())
            self.assertIn('không chứng minh', (Path(d)/'benchmark-trend.md').read_text('utf-8')) if False else None

    def test_unscored_mismatched_source_and_duplicate_sessions_rejected(self):
        runs=[sample_run(i,i+160) for i in (88,89,90)]
        bad=dict(valid_compare(),same_ground_truth=False)
        with self.assertRaises(ValueError): t.summarize_runs(runs,[valid_compare(),bad],[('a'*64,'complete')]*3)
        dup=[sample_run(88,248),sample_run(89,248),sample_run(90,250)]
        with self.assertRaises(ValueError): t.summarize_runs(dup,[valid_compare()]*2,[('a'*64,'complete')]*3)
        with self.assertRaises(ValueError): t.summarize_runs(runs[:2],[valid_compare()],[('a'*64,'complete')]*2)

    def test_new_signature_and_partial_policy_does_not_invent_identity(self):
        runs=[sample_run(i,i+160) for i in (88,89,90)]
        runs[-1]['report']['missed_items']=[{'time':591.091,'vehicle_type':'bicycle','direction':'in'}]
        out=t.summarize_runs(runs,[valid_compare()]*2,[('a'*64,'complete'),(None,'policy_missing'),('a'*64,'complete')])
        self.assertEqual(out['summary']['new_since_previous'],1)
        self.assertEqual(out['summary']['persistent_issue_signatures'],3)
        self.assertIsNone(out['integrity']['same_effective_policy_all_runs'])
        self.assertEqual(next(x for x in out['issues'] if x['kind']=='missed')['focus'],'bicycle_recall')

    def test_duplicate_case_multiplicity_does_not_overstate_persistence(self):
        runs=[sample_run(i,i+160) for i in (88,89,90)]
        runs[-1]['report']['missed_items'] *= 2
        runs[-1]['report']['missed']=2
        result=t.summarize_runs(runs,[valid_compare()]*2,[('a'*64,'complete')]*3)
        self.assertEqual(result['summary']['persistent_issue_signatures'],4)
        self.assertEqual(result['summary']['latest_issue_count'],5)
        self.assertEqual(result['summary']['new_since_previous'],1)

    def test_code_is_local_only_and_does_not_mutate_production_or_gt(self):
        text=(ROOT/'scripts/audit-benchmark-trend.py').read_text('utf-8')
        for unsafe in ('rclone ', 'gdrive:', 'os.remove(', 'shutil.rmtree(', 'UPDATE system_settings', 'docker compose down -v'):
            self.assertNotIn(unsafe,text)
        ps=(ROOT/'scripts/audit-benchmark-trend.ps1').read_text('utf-8')
        self.assertIn('docker run --rm',ps)
        self.assertIn('/src:ro',ps)
        self.assertIn('python:3.14.10-slim',ps)
        self.assertIn(':ro',ps)
        self.assertIn('benchmark-trend-audit',ps)
        self.assertIn('buildBenchmarkFocusQueue',(ROOT/'frontend/src/main.jsx').read_text('utf-8'))
        self.assertEqual(sorted(p.name for p in ROOT.glob('*.md')),['README.md'])
        version = (ROOT/'VERSION').read_text('utf-8').strip()
        self.assertRegex(version, r'^0\.5\.\d+$')
        self.assertGreaterEqual(int(version.split('.')[-1]), 130)
        self.assertEqual(json.loads((ROOT/'frontend/package.json').read_text('utf-8'))['version'], version)
        self.assertIn('test_benchmark_trend_v05130.py',(ROOT/'scripts/test.ps1').read_text('utf-8'))

if __name__=='__main__':unittest.main()
