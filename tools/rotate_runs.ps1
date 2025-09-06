$ErrorActionPreference = 'Stop'
$dir = Join-Path $PSScriptRoot '..\data\runs'
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$src = Join-Path $dir 'run.csv'
if (Test-Path $src) {
  $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
  $dst = Join-Path $dir ("run_$stamp.csv")
  Move-Item -Path $src -Destination $dst -Force
  Write-Host "Rotado a $dst"
}
# tocar nuevo run.csv vacío
New-Item -ItemType File -Force -Path $src | Out-Null
Write-Host "Nuevo $src listo"

