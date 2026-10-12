"""Source contract: raw per-ID observations and human-auditable reset counter."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
class RawProvenanceContract(unittest.TestCase):
    def test_provenance_is_not_canonical_state(self):
        code = (ROOT/'ai-service/app/tracking.py').read_text(encoding='utf-8')
        self.assertIn('self._raw_observations.get(raw_id)', code)
        self.assertIn('self._record_raw_observation(raw_id', code)
    def test_audit_reports_worker_resets_separately(self):
        code = (ROOT/'scripts/raw-id-audit.py').read_text(encoding='utf-8')
        self.assertIn('worker_raw_resets', code)
        self.assertIn('reset_increase_frames', code)
        self.assertIn('nearby_missed_gt', code)
        self.assertIn('nearby_wrong_direction', code)
if __name__ == '__main__': unittest.main()
