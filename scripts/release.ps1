[CmdletBinding()]
param(
  [string]$Owner = "TamNhien",
  [string]$Repository = "traffic-ai",
  [ValidateSet("public", "private")]
  [string]$Visibility = "private",
  [string]$Branch = "main",
  [switch]$SkipTests,
  [switch]$NoWait
)

Write-Host "[Traffic AI] release.ps1 là alias tương thích. Phiên bản luôn đọc từ file VERSION." -ForegroundColor Yellow
& "$PSScriptRoot\publish.ps1" @PSBoundParameters
exit $LASTEXITCODE
