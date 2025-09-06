<#
Rotar el archivo run.csv a un backup con timestamp y crear uno vacío.

Uso:
  pwsh -NoProfile -File scripts/rotate-run.ps1
  # o en PowerShell de Windows:
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/rotate-run.ps1
#>

$ErrorActionPreference = 'Stop'

# Carpeta de runs relativa a este script
$dir = Join-Path $PSScriptRoot '..\data\runs'

# Asegurar que exista la carpeta
New-Item -ItemType Directory -Force -Path $dir | Out-Null

$src = Join-Path $dir 'run.csv'

if (Test-Path $src) {
  $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
  $dst = Join-Path $dir ("run_$stamp.csv")
  Move-Item -Path $src -Destination $dst -Force
  Write-Host "Rotado a $dst"
}

# Tocar nuevo run.csv vacío
New-Item -ItemType File -Force -Path $src | Out-Null
Write-Host "Nuevo $src listo"

