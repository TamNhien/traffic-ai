$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Test-Path ".\gateway\certs\traffic-ai.test.crt") -or -not (Test-Path ".\gateway\certs\traffic-ai.test.key")) {
  throw "HTTPS certificate not found. Run .\scripts\generate-dev-cert.ps1 first."
}

$hostsContent = Get-Content "$env:WINDIR\System32\drivers\etc\hosts" -Raw -ErrorAction SilentlyContinue
if ($hostsContent -notmatch "(?m)^\s*127\.0\.0\.1\s+traffic-ai\.test(?:\s|$)") {
  Write-Warning "traffic-ai.test is not present in the Windows hosts file. Add: 127.0.0.1 traffic-ai.test"
}

$volume = docker volume ls --filter "name=^traffic_ai_postgres_data$" --format "{{.Name}}"
if ($volume -ne "traffic_ai_postgres_data") {
  Write-Host "[Traffic AI] Creating PostgreSQL named volume traffic_ai_postgres_data..." -ForegroundColor Yellow
  docker volume create traffic_ai_postgres_data | Out-Null
  if ($LASTEXITCODE -ne 0) {
    throw "Could not create Docker volume traffic_ai_postgres_data."
  }
}

docker compose up -d --build
if ($LASTEXITCODE -ne 0) {
  throw "docker compose up failed."
}

Write-Host "" 
Write-Host "[OK] Traffic AI started." -ForegroundColor Green
Write-Host "Dashboard : https://traffic-ai.test:8443"
Write-Host "API Docs  : https://traffic-ai.test:8444/docs"
Write-Host "PostgreSQL: 127.0.0.1:5445 / traffic_ai_db"
