[CmdletBinding()]
param([switch]$Quiet)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $root '.env'
function Read-EnvValue([string]$Key,[string]$Default) {
  if (Test-Path $envPath) {
    $m=[regex]::Match((Get-Content $envPath -Raw -Encoding UTF8), '(?m)^'+[regex]::Escape($Key)+'=(.*)$')
    if ($m.Success) { return $m.Groups[1].Value.Trim() }
  }
  return $Default
}
$db=Read-EnvValue 'POSTGRES_DB' 'traffic_ai_db'
$user=Read-EnvValue 'POSTGRES_USER' 'traffic_admin'
$pass=Read-EnvValue 'POSTGRES_PASSWORD' 'TrafficAI@2026'
$port=Read-EnvValue 'POSTGRES_HOST_PORT' '5445'
$container='traffic-ai-postgres'
$health=(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' $container 2>$null | Select-Object -First 1)
if ($LASTEXITCODE -ne 0 -or -not $health) { throw 'PostgreSQL container chưa chạy.' }
if ($health.Trim() -notin @('healthy','running')) { throw "PostgreSQL container chưa sẵn sàng: $health" }
docker exec $container pg_isready -U $user -d $db | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'pg_isready thất bại.' }
$tcp=Test-NetConnection -ComputerName 127.0.0.1 -Port ([int]$port) -WarningAction SilentlyContinue
if (-not $tcp.TcpTestSucceeded) { throw "Không kết nối được TCP 127.0.0.1:$port" }
# Validate password auth from a disposable client inside the DB container.
docker exec -e "PGPASSWORD=$pass" $container psql -h 127.0.0.1 -U $user -d $db -Atqc 'SELECT current_database(), current_user, version();' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL password authentication thất bại.' }
if (-not $Quiet) {
  Write-Host '[OK] PostgreSQL Client Guard' -ForegroundColor Green
  Write-Host "pgAdmin Host: 127.0.0.1"
  Write-Host "pgAdmin Port: $port"
  Write-Host "Database    : $db"
  Write-Host "Username    : $user"
  Write-Host 'Không dùng postgres:5432 từ Windows; hostname đó chỉ dành cho Docker network.' -ForegroundColor Yellow
}
