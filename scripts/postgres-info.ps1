[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Get-DotEnvValue([string]$Key, [string]$DefaultValue) {
  $envPath = Join-Path $root ".env"
  if (-not (Test-Path $envPath)) { return $DefaultValue }
  foreach ($line in Get-Content $envPath -Encoding UTF8) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith("#")) { continue }
    $index = $trimmed.IndexOf("=")
    if ($index -le 0) { continue }
    $name = $trimmed.Substring(0, $index).Trim()
    if ($name -ne $Key) { continue }
    return $trimmed.Substring($index + 1).Trim().Trim('"').Trim("'")
  }
  return $DefaultValue
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  throw "Docker chưa có trong PATH. Hãy mở Docker Desktop rồi chạy lại."
}

$db = Get-DotEnvValue "POSTGRES_DB" "traffic_ai_db"
$user = Get-DotEnvValue "POSTGRES_USER" "traffic_admin"
$hostPort = Get-DotEnvValue "POSTGRES_HOST_PORT" "5445"
$password = Get-DotEnvValue "POSTGRES_PASSWORD" ""
$container = "traffic-ai-postgres"

$exists = docker ps -a --filter "name=^${container}$" --format "{{.Names}}" 2>$null | Select-Object -First 1
if ($exists -ne $container) {
  Write-Host "[ERROR] Chưa có container $container." -ForegroundColor Red
  Write-Host "Chạy: .\scripts\start.ps1" -ForegroundColor Yellow
  exit 1
}

$health = (docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' $container 2>$null | Select-Object -First 1).Trim()
Write-Host "[Traffic AI] PostgreSQL container: $health" -ForegroundColor Cyan

& docker exec $container pg_isready -U $user -d $db
$ready = ($LASTEXITCODE -eq 0)

$tcpOk = $false
try {
  $tcpOk = [bool](Test-NetConnection 127.0.0.1 -Port ([int]$hostPort) -InformationLevel Quiet -WarningAction SilentlyContinue)
} catch {
  $tcpOk = $false
}

$sqlOk = $false
$sqlIdentity = $null
if ($ready -and $password) {
  # Dùng TCP + password để kiểm tra đúng kiểu đăng nhập mà pgAdmin/Backend cần.
  # Password chỉ được truyền dưới dạng env vào process psql trong container, không in ra stdout.
  $sqlIdentity = docker exec -e "PGPASSWORD=$password" $container psql -h 127.0.0.1 -p 5432 -U $user -d $db -Atc "SELECT current_database() || '|' || current_user || '|' || current_setting('server_version');" 2>$null | Select-Object -First 1
  $sqlOk = ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($sqlIdentity))
}

Write-Host ""
Write-Host "[Traffic AI] Kết nối PostgreSQL cho pgAdmin Desktop" -ForegroundColor Cyan
Write-Host "Host / Address : 127.0.0.1"
Write-Host "Port           : $hostPort"
Write-Host "Maintenance DB : $db"
Write-Host "Username       : $user"
Write-Host "Password       : lấy từ POSTGRES_PASSWORD trong .env (không in ra màn hình)"
Write-Host "SSL mode       : Prefer (mặc định)"
Write-Host ""
Write-Host "Nếu pgAdmin chạy trong cùng Docker network:" -ForegroundColor DarkCyan
Write-Host "Host / Address : postgres"
Write-Host "Port           : 5432"
Write-Host ""
Write-Host "Health         : $health"
Write-Host "pg_isready     : $ready"
Write-Host "Host TCP       : $tcpOk"
Write-Host "Password auth  : $sqlOk"
if ($sqlIdentity) { Write-Host "Identity       : $sqlIdentity" }

if (-not $password) {
  Write-Host ""
  Write-Host "[ERROR] .env chưa có POSTGRES_PASSWORD." -ForegroundColor Red
  exit 1
}
if ($health -ne "healthy" -or -not $ready -or -not $sqlOk) {
  Write-Host ""
  Write-Host "[ERROR] PostgreSQL chưa sẵn sàng hoặc password trong .env không khớp role PostgreSQL." -ForegroundColor Red
  Write-Host "Chạy chẩn đoán: .\scripts\diagnose.ps1" -ForegroundColor Yellow
  Write-Host "Nếu chỉ Password auth = False nhưng container healthy, dùng psql và lệnh \password để đồng bộ mật khẩu mà KHÔNG xóa volume." -ForegroundColor Yellow
  exit 1
}
if (-not $tcpOk) {
  Write-Host ""
  Write-Warning "PostgreSQL healthy trong Docker nhưng cổng host 127.0.0.1:$hostPort chưa truy cập được. Kiểm tra POSTGRES_HOST_PORT, Docker Desktop và xung đột cổng."
  exit 1
}

Write-Host ""
Write-Host "[OK] PostgreSQL sẵn sàng cho Backend và pgAdmin Desktop." -ForegroundColor Green
