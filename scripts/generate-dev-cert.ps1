[CmdletBinding()]
param(
  [switch]$Force
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$CertDir = Join-Path $ProjectRoot "gateway\certs"
New-Item -ItemType Directory -Force -Path $CertDir | Out-Null

$required = @(
  (Join-Path $CertDir "traffic-ai-rootCA.crt"),
  (Join-Path $CertDir "traffic-ai-rootCA.cer"),
  (Join-Path $CertDir "traffic-ai.test.crt"),
  (Join-Path $CertDir "traffic-ai.test.key")
)

if (-not $Force -and (@($required | Where-Object { -not (Test-Path $_) }).Count -eq 0)) {
  Write-Host "[OK] Certificate HTTPS local đã tồn tại; không tạo lại." -ForegroundColor Green
  return
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  throw "Không tìm thấy Docker CLI. Hãy cài/chạy Docker Desktop trước."
}

Write-Host "[Traffic AI] Tạo local CA và certificate HTTPS cho traffic-ai.test..." -ForegroundColor Cyan

$mount = ($CertDir -replace '\\','/')

docker run --rm `
  -v "${mount}:/certs" `
  alpine:3.20 sh -c @'
set -eu
apk add --no-cache openssl >/dev/null
cd /certs
rm -f traffic-ai-rootCA.key traffic-ai-rootCA.crt traffic-ai-rootCA.cer traffic-ai.test.key traffic-ai.test.csr traffic-ai.test.crt traffic-ai.test.ext traffic-ai-rootCA.srl
openssl genrsa -out traffic-ai-rootCA.key 4096
openssl req -x509 -new -nodes -key traffic-ai-rootCA.key -sha256 -days 3650 -out traffic-ai-rootCA.crt -subj "/CN=Traffic AI Local Root CA"
openssl x509 -in traffic-ai-rootCA.crt -outform der -out traffic-ai-rootCA.cer
openssl genrsa -out traffic-ai.test.key 2048
openssl req -new -key traffic-ai.test.key -out traffic-ai.test.csr -subj "/CN=traffic-ai.test"
cat > traffic-ai.test.ext <<EOT
subjectAltName=DNS:traffic-ai.test,DNS:localhost,IP:127.0.0.1
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
EOT
openssl x509 -req -in traffic-ai.test.csr -CA traffic-ai-rootCA.crt -CAkey traffic-ai-rootCA.key -CAcreateserial -out traffic-ai.test.crt -days 825 -sha256 -extfile traffic-ai.test.ext
rm -f traffic-ai.test.csr traffic-ai.test.ext traffic-ai-rootCA.srl traffic-ai-rootCA.key
'@

if ($LASTEXITCODE -ne 0) {
  throw "Tạo certificate thất bại. Hãy kiểm tra Docker Desktop và kết nối Internet cho image alpine/openssl packages."
}

Write-Host "[OK] Đã tạo certificate HTTPS local:" -ForegroundColor Green
Write-Host "  $CertDir\traffic-ai-rootCA.crt"
Write-Host "  $CertDir\traffic-ai-rootCA.cer"
Write-Host "  $CertDir\traffic-ai.test.crt"
Write-Host "  $CertDir\traffic-ai.test.key"
