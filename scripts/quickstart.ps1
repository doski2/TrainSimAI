$ErrorActionPreference = 'Stop'

Write-Host "[Quickstart] Preparando entorno..."

# Crear carpetas y archivos base
New-Item -ItemType Directory -Force -Path .\data,.\data\events,.\data\runs | Out-Null
New-Item -ItemType File -Force -Path .\data\lua_eventbus.jsonl,.\data\events\events.jsonl | Out-Null

# Variables de entorno para este proceso
$env:TSC_FAKE_RD = '1'
$env:LUA_BUS_PATH = (Join-Path $PWD 'data\lua_eventbus.jsonl')

Write-Host "[Quickstart] Ejecutando collector 5s con RD simulado..."
python -m runtime.collector --duration 5 --hz 12 | Out-Null

Write-Host "[Quickstart] Validando salida..."
python tools\validate_run.py

if (Test-Path 'tools\plot_run.py') {
  Write-Host "[Quickstart] Generando gráfico..."
  python tools\plot_run.py | Out-Null
  if (Test-Path 'plot_speed_vs_odom.png') {
    Write-Host "[Quickstart] Gráfico generado: plot_speed_vs_odom.png"
  }
}

Write-Host "[Quickstart] Listo. Puedes hacer tail en vivo con:"
Write-Host "  Get-Content .\\data\\events\\events.jsonl -Tail 50 -Wait"

