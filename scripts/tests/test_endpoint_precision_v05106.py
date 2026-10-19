"""Stdlib-only release contracts for optional endpoint precision control."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('v106_endpoint_policy',ROOT/'ai-service/app/finite_endpoint_guard.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
endpoint_precision_rejection=module.endpoint_precision_rejection

class EndpointReleaseTests(unittest.TestCase):
    def test_video_guard_enabled_with_documented_rollback(self):
        src=(ROOT/'ai-service/app/worker.py').read_text(encoding='utf-8')
        self.assertIn("os.getenv('AI_FINITE_ENDPOINT_PRECISION_GUARD', '1')",src)
        self.assertIn('finite_endpoint_center_uncertain_suppressed',src)
        self.assertIn('endpoint_precision_suppressed += 1',src)
        env=(ROOT/'.env.example').read_text(encoding='utf-8')
        self.assertIn('AI_FINITE_ENDPOINT_PRECISION_GUARD=1',env)

    def test_restrict_only_interpolated_start_endpoint(self):
        line=((0.343,0.479),(0.7587,0.385))
        p=lambda u:(line[0][0]+(line[1][0]-line[0][0])*u,line[0][1]+(line[1][1]-line[0][1])*u)
        self.assertIsNotNone(endpoint_precision_rejection(line,p(.05),.03,'out','motorcycle','interpolated'))
        self.assertIsNone(endpoint_precision_rejection(line,p(.95),.03,'out','motorcycle','interpolated'))
        self.assertIsNone(endpoint_precision_rejection(line,p(.05),.03,'out','truck','interpolated'))

    def test_worker_runtime_and_frontend_expose_counter(self):
        for path in ('ai-service/app/worker.py','ai-service/app/runtime.py','frontend/src/main.jsx'):
            self.assertIn('endpoint_precision_suppressed',(ROOT/path).read_text(encoding='utf-8'))

    def test_audit_and_powershell_commands_exist(self):
        for path in ('scripts/audit-endpoint-precision.ps1','scripts/audit-endpoint-precision.py'):
            self.assertTrue((ROOT/path).is_file())
        self.assertIn('module._verify(export)',(ROOT/'scripts/audit-endpoint-precision.py').read_text(encoding='utf-8'))

if __name__=='__main__':unittest.main()
