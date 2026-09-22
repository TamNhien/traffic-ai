$ErrorActionPreference = "Continue"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "[Traffic AI] Docker Compose status" -ForegroundColor Cyan
docker compose ps

Write-Host "`n[Traffic AI] Container health" -ForegroundColor Cyan
foreach ($name in @("traffic-ai-postgres", "traffic-ai-backend", "traffic-ai-service", "traffic-ai-frontend", "traffic-ai-gateway")) {
  try {
    $state = docker inspect --format '{{.State.Status}} / {{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' $name 2>$null
    if ($LASTEXITCODE -eq 0) { Write-Host ("{0,-24} {1}" -f $name, $state) }
  } catch {}
}

Write-Host "`n[Traffic AI] Backend logs (last 200 lines)" -ForegroundColor Cyan
docker compose logs --tail 200 backend

Write-Host "`n[Traffic AI] PostgreSQL logs (last 80 lines)" -ForegroundColor Cyan
docker compose logs --tail 80 postgres

Write-Host "`n[Traffic AI] AI service logs (last 160 lines)" -ForegroundColor Cyan
docker compose logs --tail 160 ai-service

Write-Host "`n[Traffic AI] Port checks" -ForegroundColor Cyan
Test-NetConnection 127.0.0.1 -Port 5445 -WarningAction SilentlyContinue | Select-Object ComputerName, RemotePort, TcpTestSucceeded
Test-NetConnection 127.0.0.1 -Port 8443 -WarningAction SilentlyContinue | Select-Object ComputerName, RemotePort, TcpTestSucceeded
Test-NetConnection 127.0.0.1 -Port 8444 -WarningAction SilentlyContinue | Select-Object ComputerName, RemotePort, TcpTestSucceeded

Write-Host "`n[Traffic AI] Backend health" -ForegroundColor Cyan
try { Invoke-RestMethod -SkipCertificateCheck https://traffic-ai.test:8444/api/health | ConvertTo-Json -Depth 6 } catch { Write-Warning $_.Exception.Message }

Write-Host "`n[Traffic AI] System status" -ForegroundColor Cyan
try { Invoke-RestMethod -SkipCertificateCheck https://traffic-ai.test:8444/api/system/status | ConvertTo-Json -Depth 6 } catch { Write-Warning $_.Exception.Message }

Write-Host "`n[Traffic AI] AI health" -ForegroundColor Cyan
try { Invoke-RestMethod -SkipCertificateCheck https://traffic-ai.test:8443/ai/health | ConvertTo-Json -Depth 6 } catch { Write-Warning $_.Exception.Message }
