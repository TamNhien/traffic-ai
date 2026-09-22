$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$container = docker ps -a --filter "name=^/traffic-ai-postgres$" --format "{{.Names}}"
if ($container -eq "traffic-ai-postgres") {
  Write-Host "[Traffic AI] Removing the manually-created container only." -ForegroundColor Yellow
  Write-Host "The named volume traffic_ai_postgres_data will be preserved." -ForegroundColor Yellow
  docker rm -f traffic-ai-postgres | Out-Null
}

$volume = docker volume ls --filter "name=^traffic_ai_postgres_data$" --format "{{.Name}}"
if ($volume -ne "traffic_ai_postgres_data") {
  throw "Docker volume traffic_ai_postgres_data was not found. Do not continue until the database volume is confirmed."
}

Write-Host "[OK] Existing PostgreSQL volume is ready for Docker Compose." -ForegroundColor Green
