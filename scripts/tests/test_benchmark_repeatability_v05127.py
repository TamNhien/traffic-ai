"""V0.5.127: verified benchmark rerun and non-mutating review regression tests."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT/'scripts/audit-benchmark-repeatability.py'
spec = importlib.util.spec_from_file_location('traffic_repeatability_v05127', SCRIPT)
repeat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repeat)


def issue_report():
    return {
        'missed_items': [{'time': 59.446, 'vehicle_type': 'motorcycle', 'direction': 'in', 'ground_truth_id': 1}], 'missed':1,
        'false_positive_items': [{'time': 759.52, 'vehicle_type': 'motorcycle', 'direction': 'out',
                                  'crossing_method':'direct','ai_event_id':4}], 'false_positives':1,
        'direction_mismatch_items': [{'time': 58.984, 'ground_truth_vehicle_type':'motorcycle',
                    'ground_truth_direction':'out','ai_direction':'in','crossing_method':'interpolated'}], 'direction_mismatches':1,
        'class_mismatch_items': [{'time': 641.981, 'ground_truth_vehicle_type':'car','ai_vehicle_type':'truck',
                                  'direction':'out'}], 'class_mismatches':1,
    }


def result_meta():
    return {'scoring_comparable':True, 'same_ground_truth':True,'same_source_geometry':True,
            'same_recorded_ai_crossing_signatures': True,'ai_signatures_removed_count':0,
            'ai_signatures_added_count':0,
            'prior': {'benchmark_id':88,'session_id':248,'metrics':{'missed':1}},
            'current': {'benchmark_id':89,'session_id':249,'metrics':{'missed':1}},
            'deltas': {'matched':0,'missed':0,'false_positives':0,'class_mismatches':0,'direction_mismatches':0}}

class RepeatabilityRegression(unittest.TestCase):
    def test_repeated_errors_do_not_claim_identity_or_accuracy_improvement(self):
        old=issue_report();new=issue_report()
        new['missed_items'][0]['ground_truth_id']=8392  # DB IDs differ across runs.
        summary=repeat.summarize(old,new,result_meta(),('a'*64,'complete'),('a'*64,'complete'))
        self.assertEqual(summary['issue_totals']['repeated_signatures'],4)
        self.assertEqual(summary['issue_totals']['new_signatures'],0)
        self.assertEqual(summary['issue_totals']['resolved_signatures'],0)
        self.assertTrue(summary['no_measured_improvement'])
        self.assertTrue(summary['recorded_policy']['same_effective_policy'])
        self.assertTrue(all(c['identity_proven'] is False for c in summary['issues']))
        with tempfile.TemporaryDirectory() as tmp:
            repeat.write_outputs(summary,Path(tmp))
            for fn in ('repeatability.json','repeatability.md','repeatability.csv'):
                self.assertTrue((Path(tmp)/fn).is_file())
            self.assertIn('NOT proof', (Path(tmp)/'repeatability.json').read_text('utf-8'))

    def test_changed_labels_or_direction_does_not_count_as_repeated(self):
        old=issue_report();new=issue_report()
        new['class_mismatch_items'][0]['ai_vehicle_type']='motorcycle'
        new['direction_mismatch_items'][0]['ai_direction']='out'
        summary=repeat.summarize(old,new,result_meta(),('a'*64,'complete'),('b'*64,'complete'))
        self.assertEqual(summary['issue_totals']['repeated_signatures'],2)
        self.assertEqual(summary['issue_totals']['new_signatures'],2)
        self.assertEqual(summary['issue_totals']['resolved_signatures'],2)
        self.assertFalse(summary['recorded_policy']['same_effective_policy'])

    def test_changed_gt_or_missing_scored_gt_rejected(self):
        data=result_meta()
        for k in ('same_ground_truth','scoring_comparable','same_source_geometry'):
            fail=dict(data,**{k:False})
            with self.subTest(key=k), self.assertRaises(ValueError):
                repeat.summarize(issue_report(),issue_report(),fail,('a'*64,'complete'),('a'*64,'complete'))

    def test_missing_policy_digest_does_not_claim_unchanged_policy(self):
        s=repeat.summarize(issue_report(),issue_report(),result_meta(),(None,'policy_not_recorded'),('a'*64,'complete'))
        self.assertIsNone(s['recorded_policy']['same_effective_policy'])

    def test_duplicate_case_multiplicity_and_invalid_values(self):
        old=issue_report();new=issue_report()
        new['missed_items'].append(dict(new['missed_items'][0]));new['missed']+=1
        s=repeat.summarize(old,new,result_meta(),('a'*64,'complete'),('a'*64,'complete'))
        self.assertEqual(s['issue_totals']['new_signatures'],1)
        bad=issue_report();bad['missed_items'][0]['time']=float('nan')
        with self.assertRaises(ValueError): repeat._signatures(bad)
        bad=issue_report();bad['missed_items'][0]['time']=True
        with self.assertRaises(ValueError): repeat._signatures(bad)
        bad=issue_report();bad['missed']=2
        with self.assertRaises(ValueError): repeat._signatures(bad)

    def test_version_and_delivery_contract(self):
        self.assertRegex((ROOT/'VERSION').read_text('utf-8').strip(), r'^0\.5\.\d+$')
        self.assertEqual(sorted(p.name for p in ROOT.glob('*.md')),['README.md'])
        readme=(ROOT/'README.md').read_text('utf-8')
        self.assertIn('audit-benchmark-repeatability.ps1',readme)
        source=(ROOT/'scripts/audit-benchmark-repeatability.py').read_text('utf-8')
        self.assertIn('compare-benchmark-exports.py',source)
        self.assertNotIn('docker compose down -v',source)
        self.assertNotIn('os.remove(',source)
        ps1=(ROOT/'scripts/test.ps1').read_text('utf-8')
        self.assertIn('test_benchmark_repeatability_v05127.py',ps1)
        self.assertLess(ps1.index('test_benchmark_repeatability_v05127.py'),ps1.index('Invoke-Step "Frontend build"'))

if __name__=='__main__':
    unittest.main()
