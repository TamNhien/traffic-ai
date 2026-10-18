# Native PowerShell regressions: no Docker daemon or Desktop is needed.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
. (Join-Path (Split-Path -Parent $PSScriptRoot) 'docker-engine.ps1')
$pwshPath = (Get-Process -Id $PID).Path
$checks = 0
function Assert-Check([bool]$Condition, [string]$Message) {
  if (-not $Condition) { throw "Docker readiness regression: $Message" }
  $script:checks++
}
# Real native subprocesses, covering both redirected pipes and a hung CLI.
$result = Invoke-TrafficDockerProbe -FilePath $pwshPath -Arguments @('-NoLogo', '-NoProfile', '-NonInteractive', '-Command', "[Console]::WriteLine('linux')") -TimeoutSeconds 5
Assert-Check ($result.ExitCode -eq 0 -and $result.Output -eq 'linux' -and -not $result.TimedOut) 'native process success'
$result = Invoke-TrafficDockerProbe -FilePath $pwshPath -Arguments @('-NoLogo', '-NoProfile', '-NonInteractive', '-Command', '[Console]::Out.Write("x" * 100000); [Console]::Error.Write("y" * 100000); exit 17') -TimeoutSeconds 5
Assert-Check ($result.ExitCode -eq 17 -and $result.Output.Length -eq 100000 -and -not $result.TimedOut) 'large stdout/stderr or nonzero exit'
$timer = [System.Diagnostics.Stopwatch]::StartNew()
$result = Invoke-TrafficDockerProbe -FilePath $pwshPath -Arguments @('-NoLogo', '-NoProfile', '-NonInteractive', '-Command', 'Start-Sleep -Seconds 20') -TimeoutSeconds 1
Assert-Check ($result.TimedOut -and $timer.Elapsed.TotalSeconds -lt 4) 'hung process must be terminated within a bounded deadline'
$result = Invoke-TrafficDockerProbe -FilePath (Join-Path ([System.IO.Path]::GetTempPath()) 'traffic-ai-missing-docker-command') -Arguments @('info') -TimeoutSeconds 1
Assert-Check ($result.ExitCode -ne 0 -and -not $result.TimedOut) 'missing executable must fail cleanly'

# Readiness policy mocks exist only in this child script scope.
# Keep simulated readiness messages out of the host log; only the final real test summary is shown.
function Write-Host { param($Object, $ForegroundColor) }
function Get-Command { param($Name, $CommandType, $ErrorAction); if ($script:scenario.Cli) { [pscustomobject]@{ Source = 'mock-docker' } } }
function Test-TrafficDockerWindows { return $script:scenario.Windows }
function Get-Process { param($Name, $ErrorAction); if ($script:scenario.Running) { [pscustomobject]@{ Id = 1 } } }
function Test-Path { param($LiteralPath, $PathType); return $script:scenario.Installed }
function Start-Process {
  param($FilePath, $ErrorAction)
  $script:launches++
  if ($script:scenario.LaunchFails) { throw 'simulated launch failure' }
}
function Invoke-TrafficDockerProbe {
  param($FilePath, $Arguments, $TimeoutSeconds)
  $script:calls.Add(($Arguments -join ' '))
  if ($Arguments[0] -eq 'info') {
    $index = [Math]::Min($script:infoCalls, $script:scenario.Info.Count - 1)
    $script:infoCalls++
    $value = $script:scenario.Info[$index]
    if ($value -eq 'offline') { return [pscustomobject]@{ ExitCode = 1; TimedOut = $false; Output = '' } }
    return [pscustomobject]@{ ExitCode = 0; TimedOut = $false; Output = $value }
  }
  if ($Arguments[1] -eq 'show') { return [pscustomobject]@{ ExitCode = 0; TimedOut = $false; Output = $script:scenario.Context } }
  return [pscustomobject]@{ ExitCode = $script:scenario.EndpointExit; TimedOut = $false; Output = $script:scenario.Endpoint }
}
function New-Scenario {
  $script:scenario = @{ Cli=$true; Windows=$true; Running=$false; Installed=$true; LaunchFails=$false; Info=@('offline','linux'); Context='desktop-linux'; Endpoint='npipe:////./pipe/dockerDesktopLinuxEngine'; EndpointExit=0 }
  $script:launches=0; $script:infoCalls=0
  $script:calls=[System.Collections.Generic.List[string]]::new()
  $env:DOCKER_HOST=$null; $env:DOCKER_CONTEXT=$null
}
function Invoke-ExpectedFailure([string]$MessagePattern) {
  $message = ''
  try { Assert-TrafficDockerEngine -TimeoutSeconds 10 } catch { $message = $_.Exception.Message }
  Assert-Check ($message -match $MessagePattern) "expected failure matching $MessagePattern; got: $message"
  Assert-Check ($script:launches -eq 0) 'must not launch Desktop for an unverified/unavailable endpoint'
}
$savedHost=$env:DOCKER_HOST; $savedContext=$env:DOCKER_CONTEXT
$savedProgramFiles=$env:ProgramFiles; $savedLocalAppData=$env:LOCALAPPDATA
try {
  $env:ProgramFiles=Join-Path ([System.IO.Path]::GetTempPath()) 'Traffic AI Program Files'
  $env:LOCALAPPDATA=Join-Path ([System.IO.Path]::GetTempPath()) 'Traffic AI Local App Data'
  New-Scenario; $scenario.Info=@('linux'); $scenario.Windows=$false
  Assert-TrafficDockerEngine -TimeoutSeconds 10
  Assert-Check ($infoCalls -eq 1 -and $calls.Count -eq 1 -and $launches -eq 0) 'healthy Linux daemon must return immediately without context lookup/launch'
  New-Scenario; $scenario.Cli=$false; Invoke-ExpectedFailure 'Docker CLI'
  New-Scenario; $scenario.Info=@('windows'); Invoke-ExpectedFailure 'Windows containers'
  New-Scenario; $scenario.Windows=$false; Invoke-ExpectedFailure 'Không kết nối'
  New-Scenario; $env:DOCKER_HOST='ssh://remote-host'; Invoke-ExpectedFailure 'DOCKER_HOST'
  New-Scenario; $scenario.Context='production'; Invoke-ExpectedFailure 'Không kết nối'
  New-Scenario; $scenario.Endpoint='ssh://remote-host'; Invoke-ExpectedFailure 'Không kết nối'
  New-Scenario; $scenario.EndpointExit=1; Invoke-ExpectedFailure 'Không kết nối'
  New-Scenario; $scenario.Installed=$false; Invoke-ExpectedFailure 'không tìm thấy Docker Desktop'
  New-Scenario; $scenario.LaunchFails=$true
  $message=''; try { Assert-TrafficDockerEngine -TimeoutSeconds 10 } catch { $message=$_.Exception.Message }
  Assert-Check ($message -match 'Không mở được Docker Desktop' -and $launches -eq 1) 'launch failure must be actionable, without retries'
  New-Scenario
  Assert-TrafficDockerEngine -TimeoutSeconds 10
  Assert-Check ($launches -eq 1 -and $infoCalls -eq 2) 'local stopped Desktop must launch once and become ready'
  New-Scenario; $scenario.Running=$true
  Assert-TrafficDockerEngine -TimeoutSeconds 10
  Assert-Check ($launches -eq 0 -and $infoCalls -eq 2) 'already-open Desktop must poll without relaunching'
  New-Scenario; $env:DOCKER_CONTEXT='desktop-linux'; $env:DOCKER_HOST='ssh://ignored-because-context-is-explicit'
  Assert-TrafficDockerEngine -TimeoutSeconds 10
  Assert-Check ($launches -eq 1) 'explicit context takes precedence over DOCKER_HOST'
  New-Scenario; $scenario.Info=@('offline'); $scenario.Running=$true
  $timer=[System.Diagnostics.Stopwatch]::StartNew()
  $message=''; try { Assert-TrafficDockerEngine -TimeoutSeconds 2 } catch { $message=$_.Exception.Message }
  Assert-Check ($message -match 'Không kết nối' -and $timer.Elapsed.TotalSeconds -lt 4 -and $launches -eq 0) 'Desktop readiness deadline remains bounded'
} finally {
  $env:DOCKER_HOST=$savedHost; $env:DOCKER_CONTEXT=$savedContext
  $env:ProgramFiles=$savedProgramFiles; $env:LOCALAPPDATA=$savedLocalAppData
  Remove-Item Function:Write-Host
}
Write-Host "[OK] Docker readiness native regressions: $checks assertions." -ForegroundColor Green
