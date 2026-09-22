$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$CaPath = Join-Path $ProjectRoot "gateway\certs\traffic-ai-rootCA.cer"

if (-not (Test-Path $CaPath)) {
  & (Join-Path $PSScriptRoot "generate-dev-cert.ps1")
}

& (Join-Path $PSScriptRoot "setup-local-machine.ps1") -HostName "traffic-ai.test"
