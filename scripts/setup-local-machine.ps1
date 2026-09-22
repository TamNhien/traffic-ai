[CmdletBinding()]
param(
  [string]$HostName = "traffic-ai.test"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$HostsFile = Join-Path $env:WINDIR "System32\drivers\etc\hosts"
$CaPath = Join-Path $ProjectRoot "gateway\certs\traffic-ai-rootCA.cer"

function Test-IsAdministrator {
  $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = New-Object Security.Principal.WindowsPrincipal($identity)
  return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-IsAdministrator)) {
  throw "Script này cần quyền Administrator. Hãy chạy lại bằng Run as Administrator."
}

if (-not (Test-Path $CaPath)) {
  throw "Không tìm thấy Root CA tại $CaPath."
}

$hostsRaw = Get-Content $HostsFile -Raw -ErrorAction Stop
$hostPattern = "(?m)^\s*127\.0\.0\.1\s+$([regex]::Escape($HostName))(?:\s|$)"
if ($hostsRaw -notmatch $hostPattern) {
  $backup = "$HostsFile.traffic-ai.bak"
  if (-not (Test-Path $backup)) {
    Copy-Item $HostsFile $backup -Force
  }

  Add-Content -Path $HostsFile -Value "`r`n# Traffic AI`r`n127.0.0.1 $HostName" -Encoding ascii
  Write-Host "[OK] Đã thêm 127.0.0.1 $HostName vào Windows hosts." -ForegroundColor Green
} else {
  Write-Host "[OK] Windows hosts đã có $HostName." -ForegroundColor Green
}

Write-Host "[Traffic AI] Tin cậy Traffic AI Local Root CA..." -ForegroundColor Cyan
certutil.exe -addstore -f Root $CaPath | Out-Host
if ($LASTEXITCODE -ne 0) {
  throw "Không thể import Traffic AI Local Root CA vào Trusted Root."
}

ipconfig.exe /flushdns | Out-Null
Write-Host "[OK] Cấu hình hostname và HTTPS local đã hoàn tất." -ForegroundColor Green
