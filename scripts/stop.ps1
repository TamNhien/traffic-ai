$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

docker compose down
Write-Host "[OK] Services stopped. PostgreSQL volume was preserved." -ForegroundColor Green
