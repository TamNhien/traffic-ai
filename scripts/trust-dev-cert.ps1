$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$CaPath = Join-Path $ProjectRoot "gateway\certs\traffic-ai-rootCA.crt"

if (-not (Test-Path $CaPath)) {
  throw "Root CA not found. Run .\scripts\generate-dev-cert.ps1 first."
}

Write-Host "[Traffic AI] Importing local root CA into Windows Trusted Root..." -ForegroundColor Cyan
certutil.exe -addstore -f Root $CaPath
if ($LASTEXITCODE -ne 0) {
  throw "Could not trust the certificate. Run PowerShell as Administrator."
}
Write-Host "[OK] Traffic AI Local Root CA is trusted." -ForegroundColor Green
