$ErrorActionPreference = "Continue"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "[Traffic AI] Docker Compose status" -ForegroundColor Cyan
docker compose ps

Write-Host "`n[Traffic AI] Backend logs (last 120 lines)" -ForegroundColor Cyan
docker compose logs --tail 120 backend

Write-Host "`n[Traffic AI] PostgreSQL logs (last 60 lines)" -ForegroundColor Cyan
docker compose logs --tail 60 postgres

Write-Host "`n[Traffic AI] AI service logs (last 60 lines)" -ForegroundColor Cyan
docker compose logs --tail 60 ai-service

Write-Host "`n[Traffic AI] Port checks" -ForegroundColor Cyan
Test-NetConnection 127.0.0.1 -Port 5445 -WarningAction SilentlyContinue | Select-Object ComputerName, RemotePort, TcpTestSucceeded
Test-NetConnection 127.0.0.1 -Port 8443 -WarningAction SilentlyContinue | Select-Object ComputerName, RemotePort, TcpTestSucceeded
Test-NetConnection 127.0.0.1 -Port 8444 -WarningAction SilentlyContinue | Select-Object ComputerName, RemotePort, TcpTestSucceeded
