param()
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
Write-Host "[Traffic AI] Container status (no secrets / no volumes removed)" -ForegroundColor Cyan
docker compose -f docker-compose.yml ps -a
Write-Host "`n[Traffic AI] PostgreSQL recent logs" -ForegroundColor Yellow
docker compose -f docker-compose.yml logs --tail 80 postgres
Write-Host "`n[Traffic AI] Backend recent logs" -ForegroundColor Yellow
docker compose -f docker-compose.yml logs --tail 160 backend
Write-Host "`n[Traffic AI] Backend healthcheck result" -ForegroundColor Yellow
docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{range .State.Health.Log}}{{println .ExitCode .Output}}{{end}}{{else}}{{.State.Status}}{{end}}' traffic-ai-backend
Write-Host "`n[Traffic AI] No database files or volumes were modified." -ForegroundColor Green
