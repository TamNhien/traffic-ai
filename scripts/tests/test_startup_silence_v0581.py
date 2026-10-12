"""Regression contract for silent, bounded startup and disposable pip installs."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
START = (ROOT / 'scripts/start.ps1').read_text('utf-8')
TEST = (ROOT / 'scripts/test.ps1').read_text('utf-8')


class QuietStartupContract(unittest.TestCase):
    def test_wait_remains_bounded_and_polls_health(self):
        body = START.split('function Wait-ContainerHealthy', 1)[1].split('function Test-HttpsEndpoint', 1)[0]
        self.assertIn('[System.Diagnostics.Stopwatch]::StartNew()', body)
        self.assertIn('$timer.Elapsed.TotalSeconds -lt $TimeoutSeconds', body)
        self.assertIn('Get-ContainerHealth $Name', body)
        self.assertIn('Start-Sleep -Seconds 3', body)
        self.assertIn("@('unhealthy', 'exited', 'dead')", body)
        self.assertIn('return $false', body)
        self.assertIn('Timed out after $TimeoutSeconds', body)

    def test_wait_has_no_timer_in_normal_output(self):
        body = START.split('function Wait-ContainerHealthy', 1)[1].split('function Test-HttpsEndpoint', 1)[0]
        self.assertNotIn('Waiting for $Name (', body)
        self.assertNotIn('healthy after', body)
        self.assertIn('Write-Host "[OK] $Name healthy."', body)
        self.assertNotRegex(body, r'Write-Host[^\n]*timer\.Elapsed')

    def test_backup_worker_pip_warning_is_suppressed_only_in_disposable_container(self):
        body = TEST.split('Invoke-Step "Backup worker syntax + unit tests"', 1)[1].split('Invoke-Step "AI service syntax check"', 1)[0]
        self.assertIn('docker run --rm', body)
        self.assertIn('-e PIP_ROOT_USER_ACTION=ignore', body)
        self.assertIn('-e PIP_DISABLE_PIP_VERSION_CHECK=1', body)
        self.assertIn('python -m pytest -q test_worker.py', body)
        self.assertNotIn('--privileged', body)

    def test_startup_errors_are_not_suppressed(self):
        self.assertIn('Show-StartupDiagnostics', START)
        self.assertIn('Show-GatewayDiagnostics', START)
        self.assertIn('throw "Backend did not become healthy', START)
        self.assertIn('throw "AI Service did not become healthy', START)


if __name__ == '__main__':
    unittest.main()
