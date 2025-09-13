@echo off
setlocal enabledelayedexpansion
REM -- Detectar el último CSV de control
for /f "delims=" %%F in ('powershell -NoProfile -Command ^
  "$f=(Get-ChildItem -ErrorAction SilentlyContinue -File 'data\\runs\\ctrl_live_*.csv' | Sort-Object LastWriteTime | Select-Object -Last 1).FullName; ^
   if(-not $f -and (Test-Path 'data\\ctrl_live.csv')){ $f='data\\ctrl_live.csv' }; ^
   if($f){Write-Output $f}"') do (set "CSV=%%F")
if not defined CSV (
  echo [tsc_kpi] No se encontro CSV en data\runs\ctrl_live_*.csv ni data\ctrl_live.csv
  exit /b 1
)
echo [tsc_kpi] CSV: %CSV%
python -m tools.validate_kpi --csv "%CSV%" --arrival-dist-m 8 --arrival-vmargin-kph 0.5 --window-m 50 --monotonicity-bump-m 2 --min-arrivals-ok 0.90
exit /b %errorlevel%
