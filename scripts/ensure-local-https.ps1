[CmdletBinding()]
param(
  [string]$HostName = "traffic-ai.test"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$CertDir = Join-Path $ProjectRoot "gateway\certs"
$ServerCert = Join-Path $CertDir "$HostName.crt"
$ServerKey = Join-Path $CertDir "$HostName.key"
$CaPath = Join-Path $CertDir "traffic-ai-rootCA.cer"
$HostsFile = Join-Path $env:WINDIR "System32\drivers\etc\hosts"
$SetupScript = Join-Path $PSScriptRoot "setup-local-machine.ps1"

function Test-IsAdministrator {
  $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = New-Object Security.Principal.WindowsPrincipal($identity)
  return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-HostMapping {
  if (-not (Test-Path $HostsFile)) { return $false }
  $raw = Get-Content $HostsFile -Raw -ErrorAction SilentlyContinue
  $pattern = "(?m)^\s*127\.0\.0\.1\s+$([regex]::Escape($HostName))(?:\s|$)"
  return ($raw -match $pattern)
}

function Test-RootTrusted {
  if (-not (Test-Path $CaPath)) { return $false }
  try {
    $ca = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($CaPath)
    if (-not $ca -or -not $ca.Thumbprint) { return $false }
    return (Test-Path "Cert:\LocalMachine\Root\$($ca.Thumbprint)")
  } catch {
    return $false
  }
}

$missing = @($ServerCert, $ServerKey, $CaPath) | Where-Object { -not (Test-Path $_) }
if ($missing.Count -gt 0) {
  Write-Host "[Traffic AI] Chưa có certificate HTTPS local. Đang tạo tự động..." -ForegroundColor Yellow
  & (Join-Path $PSScriptRoot "generate-dev-cert.ps1")
  if ($LASTEXITCODE -ne 0) {
    throw "Không thể tạo certificate HTTPS local."
  }
}

$needsHost = -not (Test-HostMapping)
$needsTrust = -not (Test-RootTrusted)

if ($needsHost -or $needsTrust) {
  Write-Host "[Traffic AI] Cần cấu hình Windows hosts/Trusted Root lần đầu." -ForegroundColor Yellow

  if (Test-IsAdministrator) {
    & $SetupScript -HostName $HostName
    if ($LASTEXITCODE -ne 0) { throw "Cấu hình HTTPS local thất bại." }
  } else {
    Write-Host "[Traffic AI] Windows sẽ hiện UAC. Hãy chọn Yes để hoàn tất cấu hình HTTPS local." -ForegroundColor Cyan
    $shell = (Get-Process -Id $PID).Path
    $argLine = "-NoProfile -ExecutionPolicy Bypass -File `"$SetupScript`" -HostName `"$HostName`""
    try {
      $proc = Start-Process -FilePath $shell -Verb RunAs -ArgumentList $argLine -Wait -PassThru
    } catch {
      throw "Bạn đã hủy hoặc Windows không cho phép nâng quyền. Không thể tự cấu hình hosts/HTTPS. Chi tiết: $($_.Exception.Message)"
    }
    if ($proc.ExitCode -ne 0) {
      throw "Cấu hình hosts/HTTPS bằng quyền Administrator thất bại với exit code $($proc.ExitCode)."
    }
  }
}

if (-not (Test-HostMapping)) {
  throw "traffic-ai.test chưa được ánh xạ về 127.0.0.1 trong Windows hosts."
}
if (-not (Test-RootTrusted)) {
  throw "Traffic AI Local Root CA chưa được tin cậy trong LocalMachine Trusted Root."
}
if (-not (Test-Path $ServerCert) -or -not (Test-Path $ServerKey)) {
  throw "Certificate HTTPS server vẫn chưa đầy đủ sau bước bootstrap."
}

Write-Host "[OK] HTTPS local sẵn sàng: https://$HostName`:8443" -ForegroundColor Green
