"""Docker readiness ordering/safety contracts; native behavior runs in PowerShell.

The native harness is also run by scripts/test.ps1 on the host before its first
Docker call. Docker's Python test container does not need PowerShell installed.
"""
from pathlib import Path
import re
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
HELPER = (ROOT / "scripts/docker-engine.ps1").read_text("utf-8")
START = (ROOT / "scripts/start.ps1").read_text("utf-8")
TEST = (ROOT / "scripts/test.ps1").read_text("utf-8")
HARNESS = ROOT / "scripts/tests/test-docker-engine-v0595.ps1"


class DockerReadinessContract(unittest.TestCase):
    def test_start_checks_engine_before_env_cert_or_volume(self):
        guard = START.index("\nAssert-TrafficDockerEngine\n")
        for side_effect in ('Copy-Item ".\\.env.example"', 'WriteAllText(', 'ensure-local-https.ps1', '$volume = docker volume ls', '$existingDbVolume = docker volume ls'):
            with self.subTest(side_effect=side_effect):
                self.assertLess(guard, START.index(side_effect))

    def test_test_checks_engine_before_first_docker_invocation(self):
        calls = TEST[TEST.index('Write-Host \'[OK] V0.5.78 Direct Shadow Evidence Gate\''):]
        self.assertLess(calls.index('Assert-TrafficDockerEngine'), calls.index('docker run --rm'))
        self.assertLess(calls.index('tests/test-docker-engine-v0595.ps1'), calls.index('Assert-TrafficDockerEngine'))
        self.assertIn('test_docker_engine_v0595.py', TEST)

    def test_failed_volume_query_is_not_absence(self):
        for variable in ('$volume', '$existingDbVolume'):
            query = START.index(f'{variable} = docker volume ls')
            next_if = START[query:].split('\n', 2)[1]
            self.assertRegex(next_if, r'\$LASTEXITCODE -ne 0.*throw')
        second = START.index('$volume = docker volume ls')
        self.assertLess(START.index('$LASTEXITCODE -ne 0', second), START.index('docker volume create', second))

    def test_process_probe_has_deadline_and_concurrent_pipe_drain(self):
        body = HELPER.split('function Test-TrafficDockerWindows')[0]
        self.assertIn('UseShellExecute = $false', body)
        self.assertIn('ArgumentList.Add($argument)', body)
        self.assertIn('StandardOutput.ReadToEndAsync()', body)
        self.assertIn('StandardError.ReadToEndAsync()', body)
        self.assertIn('$TimeoutSeconds * 1000 - $probeTimer.Elapsed.TotalMilliseconds', body)
        self.assertIn('WaitForExit($remainingMs)', body)
        self.assertIn('@($stdout, $stderr), $remainingMs)', body)
        self.assertIn('$process.Kill($true)', body)
        self.assertIn('Task]::WaitAll', body)
        self.assertNotIn('WaitForExit()', body)
        self.assertIn('$process.Dispose()', body)

    def test_no_endpoint_service_or_data_mutations(self):
        executable_lines = '\n'.join(line for line in HELPER.splitlines() if not line.lstrip().startswith('#'))
        for forbidden in (r'context\s+use', r'volume\s+(?:create|rm|prune)', r'Start-Service', r'Restart-Service', r'wsl(?:\.exe)?\b', r'-Verb\s+RunAs', r'Set-Content', r'Remove-Item', r'Invoke-Expression'):
            with self.subTest(forbidden=forbidden):
                self.assertNotRegex(executable_lines, re.compile(forbidden, re.I))
        self.assertNotIn('$stderr.Result', HELPER)
        self.assertNotIn('Write-Host $probe.Output', HELPER)

    def test_desktop_autostart_requires_verified_local_linux_context(self):
        policy = HELPER[HELPER.index('function Assert-TrafficDockerEngine'):]
        launch = policy.index('Start-Process -FilePath $desktopPath')
        for prerequisite in ('if (-not (Test-TrafficDockerWindows))', '$env:DOCKER_CONTEXT -and $env:DOCKER_HOST', "$contextProbe.Output -ne 'desktop-linux'", 'dockerDesktopLinuxEngine/?$', 'if (-not $desktopRunning)', 'if (-not $desktopPath)'):
            with self.subTest(prerequisite=prerequisite):
                self.assertLess(policy.index(prerequisite), launch)
        self.assertEqual(1, policy.count('Start-Process -FilePath'))

    def test_healthy_linux_returns_before_context_and_windows_engine_fails(self):
        policy = HELPER[HELPER.index('function Assert-TrafficDockerEngine'):]
        self.assertLess(policy.index("$probe.Output -eq 'linux') { return }"), policy.index("@('context', 'show')"))
        self.assertLess(policy.index("$probe.Output -eq 'windows'"), policy.index('Start-Process -FilePath'))
        self.assertIn('[ValidateRange(1, 120)][int]$TimeoutSeconds = 120', policy)
        self.assertIn('$timer.Elapsed.TotalSeconds -lt $TimeoutSeconds', policy)

    def test_native_harness_covers_daemon_free_failure_and_recovery(self):
        harness = HARNESS.read_text('utf-8')
        for scenario in ('large stdout/stderr', 'hung process', 'missing executable', 'Windows containers', 'ssh://remote-host', "Context='desktop-linux'", "Context='production'", '$scenario.Installed=$false', '$scenario.LaunchFails=$true', 'local stopped Desktop', 'already-open Desktop', 'precedence over DOCKER_HOST', 'deadline remains bounded'):
            with self.subTest(scenario=scenario):
                self.assertIn(scenario, harness)
        self.assertIn('finally {', harness)
        self.assertIn('$env:DOCKER_HOST=$savedHost', harness)


@unittest.skipUnless(shutil.which('pwsh'), 'PowerShell is unavailable; native harness runs on host in scripts/test.ps1')
class NativeDockerReadinessRegression(unittest.TestCase):
    def test_native_process_and_readiness_scenarios(self):
        result = subprocess.run([shutil.which('pwsh'), '-NoLogo', '-NoProfile', '-NonInteractive', '-File', str(HARNESS)], capture_output=True, text=True, timeout=45)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn('Docker readiness native regressions:', result.stdout)


if __name__ == '__main__':
    unittest.main()
