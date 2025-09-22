$ErrorActionPreference = 'Stop'
$paths = @(
  "data\runs\*.csv",
  "data\events\events.jsonl",
  "plot_speed_vs_odom.png",
  "events_timeline.csv",
  ".tmp_run\*"
)
foreach ($p in $paths) {
  Get-ChildItem $p -ErrorAction SilentlyContinue | Remove-Item -Force -Recurse -ErrorAction SilentlyContinue
}
New-Item -ItemType File -Force -Path data\runs\.gitkeep | Out-Null
New-Item -ItemType File -Force -Path data\events\.gitkeep | Out-Null
Write-Host "[OK] Limpieza completada."
