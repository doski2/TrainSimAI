param(
  [string]$RepoPath = $(Split-Path -Parent $MyInvocation.MyCommand.Path)
)

$repo = Resolve-Path (Join-Path $RepoPath '..')
Push-Location $repo

try {
  # 1) Generar/actualizar el resumen diario
  python scripts/generate_daily_summary.py

  if ($LASTEXITCODE -ne 0) {
    Write-Error "Fallo al generar el resumen diario"
    exit 1
  }

  # 2) Añadir solo el directorio de diario al índice
  git add -- docs/diario/ 2>$null | Out-Null

  # 3) Si no hay cambios staged, salir sin hacer nada
  git diff --cached --quiet
  if ($LASTEXITCODE -eq 0) {
    Write-Output "[diario] Sin cambios para publicar."
    exit 0
  }

  # 4) Construir mensaje de commit y detectar rama actual
  $date = Get-Date -Format 'yyyy-MM-dd HH:mm'
  $branch = (git rev-parse --abbrev-ref HEAD).Trim()
  if (-not $branch) { $branch = 'main' }

  $msg = "docs: actualizar diario $date"
  git commit -m $msg | Out-Null

  # 5) Hacer push a origin/<branch>
  git push origin $branch
  if ($LASTEXITCODE -ne 0) {
    Write-Error "Fallo al hacer push a origin/$branch"
    exit 1
  }

  Write-Output "[diario] Cambios publicados en origin/$branch"
}
finally {
  Pop-Location
}
