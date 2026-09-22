$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

docker compose ps
Write-Host ""
Write-Host "Checking HTTPS endpoints..." -ForegroundColor Cyan
try {
  $health = Invoke-RestMethod -Uri "https://traffic-ai.test:8443/api/health" -TimeoutSec 5
  $health | ConvertTo-Json -Depth 5
} catch {
  Write-Warning $_.Exception.Message
}
