# Shared readiness check. Dot-source this file; it does not start Docker on import.
# No context, service, WSL, volume, container or application data is changed.
function Invoke-TrafficDockerProbe {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory)][string]$FilePath,
    [Parameter(Mandatory)][string[]]$Arguments,
    [ValidateRange(1, 120)][int]$TimeoutSeconds = 5
  )
  $process = [System.Diagnostics.Process]::new()
  $process.StartInfo = [System.Diagnostics.ProcessStartInfo]::new()
  $process.StartInfo.FileName = $FilePath
  $process.StartInfo.UseShellExecute = $false
  $process.StartInfo.CreateNoWindow = $true
  $process.StartInfo.RedirectStandardOutput = $true
  $process.StartInfo.RedirectStandardError = $true
  foreach ($argument in $Arguments) { $process.StartInfo.ArgumentList.Add($argument) }
  $probeTimer = [System.Diagnostics.Stopwatch]::StartNew()
  try {
    if (-not $process.Start()) { throw 'Docker CLI process did not start.' }
    # Drain both pipes concurrently, including on timeout, to avoid pipe deadlocks.
    $stdout = $process.StandardOutput.ReadToEndAsync()
    $stderr = $process.StandardError.ReadToEndAsync()
    $remainingMs = [Math]::Max(0, [int][Math]::Floor($TimeoutSeconds * 1000 - $probeTimer.Elapsed.TotalMilliseconds))
    if (-not $process.WaitForExit($remainingMs)) {
      try { $process.Kill($true) } catch { try { $process.Kill() } catch {} }
      return [pscustomobject]@{ ExitCode = -1; TimedOut = $true; Output = '' }
    }
    # A child retaining a pipe handle must not defeat the process deadline.
    $remainingMs = [Math]::Max(0, [int][Math]::Floor($TimeoutSeconds * 1000 - $probeTimer.Elapsed.TotalMilliseconds))
    if (-not [System.Threading.Tasks.Task]::WaitAll([System.Threading.Tasks.Task[]]@($stdout, $stderr), $remainingMs)) {
      return [pscustomobject]@{ ExitCode = -1; TimedOut = $true; Output = '' }
    }
    return [pscustomobject]@{ ExitCode = $process.ExitCode; TimedOut = $false; Output = $stdout.Result.Trim() }
  } catch {
    return [pscustomobject]@{ ExitCode = -1; TimedOut = $false; Output = '' }
  } finally {
    $process.Dispose()
  }
}

function Test-TrafficDockerWindows { return $IsWindows }

function Assert-TrafficDockerEngine {
  [CmdletBinding()]
  param([ValidateRange(1, 120)][int]$TimeoutSeconds = 120)

  $dockerCommand = Get-Command docker -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
  if (-not $dockerCommand) {
    throw 'Không tìm thấy Docker CLI. Cài Docker Desktop, mở lại PowerShell rồi chạy lại lệnh.'
  }
  $dockerPath = $dockerCommand.Source
  $timer = [System.Diagnostics.Stopwatch]::StartNew()
  $probeSeconds = [Math]::Min(5, $TimeoutSeconds)
  $probe = Invoke-TrafficDockerProbe -FilePath $dockerPath -Arguments @('info', '--format', '{{.OSType}}') -TimeoutSeconds $probeSeconds
  if ($probe.ExitCode -eq 0 -and $probe.Output -eq 'linux') { return }
  if ($probe.ExitCode -eq 0 -and $probe.Output -eq 'windows') {
    throw 'Docker đang chạy Windows containers. Chuyển Docker Desktop sang Linux containers rồi chạy lại lệnh.'
  }
  $unavailable = 'Không kết nối được Docker Linux engine. Mở Docker Desktop, chờ Engine running rồi chạy lại. Có thể kiểm tra bằng: docker info --format "{{.OSType}}". Không tạo hay xóa PostgreSQL volume khi engine chưa sẵn sàng.'
  if (-not (Test-TrafficDockerWindows)) { throw $unavailable }

  # Respect explicit endpoint/context selection. Never auto-launch for a remote
  # endpoint, a custom context, or an endpoint whose local identity is unproven.
  if (-not $env:DOCKER_CONTEXT -and $env:DOCKER_HOST) {
    throw 'Docker endpoint đang được chọn qua DOCKER_HOST và chưa sẵn sàng. Kiểm tra endpoint đã cấu hình rồi chạy lại; script không tự đổi endpoint hay Docker context.'
  }
  $remaining = [int][Math]::Floor($TimeoutSeconds - $timer.Elapsed.TotalSeconds)
  if ($remaining -lt 1) { throw $unavailable }
  $contextProbe = Invoke-TrafficDockerProbe -FilePath $dockerPath -Arguments @('context', 'show') -TimeoutSeconds ([Math]::Min(5, $remaining))
  if ($contextProbe.ExitCode -ne 0 -or $contextProbe.Output -ne 'desktop-linux') { throw $unavailable }
  $remaining = [int][Math]::Floor($TimeoutSeconds - $timer.Elapsed.TotalSeconds)
  if ($remaining -lt 1) { throw $unavailable }
  $endpointProbe = Invoke-TrafficDockerProbe -FilePath $dockerPath -Arguments @('context', 'inspect', 'desktop-linux', '--format', '{{.Endpoints.docker.Host}}') -TimeoutSeconds ([Math]::Min(5, $remaining))
  if ($endpointProbe.ExitCode -ne 0 -or $endpointProbe.Output -notmatch '^npipe:/{2,}\./pipe/dockerDesktopLinuxEngine/?$') { throw $unavailable }

  $desktopRunning = Get-Process -Name 'Docker Desktop' -ErrorAction SilentlyContinue
  if (-not $desktopRunning) {
    $desktopCandidates = @()
    if ($env:ProgramFiles) { $desktopCandidates += Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe' }
    if ($env:LOCALAPPDATA) {
      $desktopCandidates += Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\Docker Desktop.exe'
      $desktopCandidates += Join-Path $env:LOCALAPPDATA 'Docker\Docker Desktop.exe'
    }
    $desktopPath = $desktopCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
    if (-not $desktopPath) {
      throw 'Docker Desktop Linux engine chưa sẵn sàng và không tìm thấy Docker Desktop ở thư mục cài đặt thông thường. Mở Docker Desktop thủ công, chờ Engine running rồi chạy lại.'
    }
    try { Start-Process -FilePath $desktopPath -ErrorAction Stop | Out-Null } catch {
      throw 'Không mở được Docker Desktop. Mở ứng dụng thủ công, chờ Linux engine sẵn sàng rồi chạy lại.'
    }
    Write-Host '[Traffic AI] Đã mở Docker Desktop; đang chờ Linux engine sẵn sàng.' -ForegroundColor Cyan
  } else {
    Write-Host '[Traffic AI] Docker Desktop đang mở; đang chờ Linux engine sẵn sàng.' -ForegroundColor Cyan
  }
  while ($timer.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
    $remaining = [int][Math]::Floor($TimeoutSeconds - $timer.Elapsed.TotalSeconds)
    if ($remaining -lt 1) { break }
    $probe = Invoke-TrafficDockerProbe -FilePath $dockerPath -Arguments @('info', '--format', '{{.OSType}}') -TimeoutSeconds ([Math]::Min(5, $remaining))
    if ($probe.ExitCode -eq 0 -and $probe.Output -eq 'linux') {
      Write-Host '[OK] Docker Linux engine sẵn sàng.' -ForegroundColor Green
      return
    }
    if ($probe.ExitCode -eq 0 -and $probe.Output -eq 'windows') {
      throw 'Docker đang chạy Windows containers. Chuyển Docker Desktop sang Linux containers rồi chạy lại lệnh.'
    }
    $remainingMs = [int][Math]::Floor(($TimeoutSeconds - $timer.Elapsed.TotalSeconds) * 1000)
    if ($remainingMs -gt 0) { Start-Sleep -Milliseconds ([Math]::Min(2000, $remainingMs)) }
  }
  throw $unavailable
}
