@echo off
setlocal ENABLEDELAYEDEXPANSION
title TSC – Sim
pushd "%~dp0\.."

if not exist ".venv\Scripts\activate.bat" (
  echo [!] No se encuentra .venv. Crea el entorno:  python -m venv .venv  &&  .venv\Scripts\activate && pip install -r requirements.txt
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"

rem === Config por defecto ===
set TSC_FAKE_RD=1
set RUN_CSV=data\runs\run.csv
set EVENTS=data\events.jsonl
set PROFILE=profiles\BR146.json
set OUT=data\ctrl_live.csv

if not exist "data\runs" mkdir "data\runs"
if not exist "data" mkdir "data"
del /q "%OUT%" 2>nul

start "TSC Collector (sim)" cmd /k "python -m runtime.collector --hz 10 --bus-from-start"
timeout /t 2 >nul
start "TSC Control Loop" cmd /k "python -m runtime.control_loop --run %RUN_CSV% --events %EVENTS% --profile %PROFILE% --hz 5 --start-events-from-end --out %OUT%"
start "Tail ctrl_live" powershell -NoLogo -NoProfile -Command "while(!(Test-Path '%OUT%')){Start-Sleep 0.5}; Get-Content '%OUT%' -Tail 10 -Wait"

popd
endlocal
