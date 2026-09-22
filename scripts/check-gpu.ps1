$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "[Traffic AI] Host NVIDIA GPU" -ForegroundColor Cyan
nvidia-smi

Write-Host "`n[Traffic AI] AI container CUDA status" -ForegroundColor Cyan
try {
  Invoke-RestMethod -SkipCertificateCheck https://traffic-ai.test:8443/ai/health | ConvertTo-Json -Depth 6
} catch {
  Write-Warning $_.Exception.Message
  Write-Host "If the system is not running, execute: .\scripts\start.ps1" -ForegroundColor Yellow
}
