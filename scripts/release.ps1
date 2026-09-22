[CmdletBinding()]
param(
  [ValidatePattern('^\d+\.\d+\.\d+$')]
  [string]$Version,
  [string]$Owner = "TamNhien",
  [string]$Repository = "traffic-ai",
  [ValidateSet("public", "private")]
  [string]$Visibility = "private",
  [string]$Branch = "main",
  [switch]$SkipTests,
  [switch]$NoWait
)

# Giữ tương thích với lệnh cũ; quy trình chính đã được gom vào publish.ps1.
& "$PSScriptRoot\publish.ps1" @PSBoundParameters
exit $LASTEXITCODE
