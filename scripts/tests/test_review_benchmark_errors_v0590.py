"""V0.5.90: no GT editing, evidence-first error review queue."""
from __future__ import annotations
import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from test_compare_benchmark_exports_v0587 import make_benchmark, mark_unscored

SCRIPT = Path(__file__).resolve().parents[1] / 'review-benchmark-errors.py'
spec = importlib.util.spec_from_file_location('traffic_review_benchmark_errors', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class VerifiedReviewQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.archive = Path(self.tmp.name) / 'input.zip'

    def test_verified_scored_report_yields_all_missed_and_extra_once(self):
        make_benchmark(self.archive, 1, gt_time=1, ai_time=3)
        r = module.build_queue(self.archive)
        self.assertEqual((r['case_count'], r['missed'], r['extra']), (2, 1, 1))
        self.assertEqual([c['case_id'] for c in r['cases']], ['GT-01', 'AI-01'])
        self.assertTrue(all(c['identity_proven'] is False for c in r['cases']))
        self.assertTrue(all(not c['nearby_opposite_case_ids'] for c in r['cases']))

    def test_requires_gt_without_guessing_score(self):
        make_benchmark(self.archive, 1)
        mark_unscored(self.archive)
        with self.assertRaisesRegex(ValueError, 'chưa có GT'):
            module.build_queue(self.archive)

    def test_csv_md_json_outputs_complete_and_excel_friendly(self):
        make_benchmark(self.archive, 1, gt_time=1, ai_time=3)
        output = Path(self.tmp.name)/'out'
        module.write_queue(module.build_queue(self.archive), output)
        self.assertIn('lọt **1**', (output/'review-queue.md').read_text(encoding='utf-8'))
        with (output/'review-queue.csv').open(encoding='utf-8-sig',newline='') as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['timecode'], '00:00:01.000')
        self.assertEqual(json.loads((output/'review-queue.json').read_text())['case_count'], 2)

    def test_rejects_broken_trace_digest_even_if_json_valid(self):
        import zipfile
        make_benchmark(self.archive, 1, gt_time=1, ai_time=3)
        with zipfile.ZipFile(self.archive) as z:
            blobs = {name:z.read(name) for name in z.namelist()}
        blobs['benchmark-trace.jsonl'] = b'not original evidence'
        with zipfile.ZipFile(self.archive,'w') as z:
            for k,v in blobs.items():z.writestr(k,v)
        with self.assertRaisesRegex(ValueError, 'digest mismatch|trace length mismatch'):
            module.build_queue(self.archive)

    def test_window_must_be_bounded(self):
        make_benchmark(self.archive, 1)
        with self.assertRaisesRegex(ValueError, 'Review window'):
            module.build_queue(self.archive, near_window=8.0)

if __name__=='__main__':
    unittest.main()
