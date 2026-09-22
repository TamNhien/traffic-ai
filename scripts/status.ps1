$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

docker compose ps

Write-Host "`nBackend health:" -ForegroundColor Cyan
try { Invoke-RestMethod -SkipCertificateCheck https://traffic-ai.test:8444/api/health | ConvertTo-Json -Depth 5 } catch { Write-Warning $_.Exception.Message }

Write-Host "`nSystem status:" -ForegroundColor Cyan
try { Invoke-RestMethod -SkipCertificateCheck https://traffic-ai.test:8444/api/system/status | ConvertTo-Json -Depth 6 } catch { Write-Warning $_.Exception.Message }

Write-Host "`nAI health:" -ForegroundColor Cyan
try { Invoke-RestMethod -SkipCertificateCheck https://traffic-ai.test:8443/ai/health | ConvertTo-Json -Depth 5 } catch { Write-Warning $_.Exception.Message }
