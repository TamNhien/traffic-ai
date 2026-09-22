$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$CertDir = Join-Path $ProjectRoot "gateway\certs"
New-Item -ItemType Directory -Force -Path $CertDir | Out-Null

Write-Host "[Traffic AI] Generating local CA and HTTPS certificate..." -ForegroundColor Cyan

$mount = ($CertDir -replace '\\','/')

docker run --rm `
  -v "${mount}:/certs" `
  alpine:3.20 sh -c @'
set -eu
apk add --no-cache openssl >/dev/null
cd /certs
rm -f traffic-ai-rootCA.key traffic-ai-rootCA.crt traffic-ai.test.key traffic-ai.test.csr traffic-ai.test.crt traffic-ai.test.ext traffic-ai-rootCA.srl
openssl genrsa -out traffic-ai-rootCA.key 4096
openssl req -x509 -new -nodes -key traffic-ai-rootCA.key -sha256 -days 3650 -out traffic-ai-rootCA.crt -subj "/CN=Traffic AI Local Root CA"
openssl genrsa -out traffic-ai.test.key 2048
openssl req -new -key traffic-ai.test.key -out traffic-ai.test.csr -subj "/CN=traffic-ai.test"
cat > traffic-ai.test.ext <<EOT
subjectAltName=DNS:traffic-ai.test,DNS:localhost,IP:127.0.0.1
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
EOT
openssl x509 -req -in traffic-ai.test.csr -CA traffic-ai-rootCA.crt -CAkey traffic-ai-rootCA.key -CAcreateserial -out traffic-ai.test.crt -days 825 -sha256 -extfile traffic-ai.test.ext
rm -f traffic-ai.test.csr traffic-ai.test.ext traffic-ai-rootCA.srl
'@

if ($LASTEXITCODE -ne 0) {
  throw "Certificate generation failed. Make sure Docker Desktop is running."
}

Write-Host "[OK] Certificate created:" -ForegroundColor Green
Write-Host "  $CertDir\traffic-ai.test.crt"
Write-Host "  $CertDir\traffic-ai.test.key"
Write-Host ""
Write-Host "Next, run PowerShell as Administrator and execute:" -ForegroundColor Yellow
Write-Host "  .\scripts\trust-dev-cert.ps1"
