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

# Giữ tương thích với tên script cũ; từ V0.1.4 lệnh này cũng phát hành Release.
& "$PSScriptRoot\publish.ps1" @PSBoundParameters
exit $LASTEXITCODE
