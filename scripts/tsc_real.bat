REM Modo (permite override por variable de entorno)
if not defined TSC_MODE set "TSC_MODE=brake"
REM Proveedor de RD (modulo:atributo), opcional
REM Ejemplos:
REM   set TSC_RD=runtime.raildriver_stub:rd
REM   set TSC_RD=miwrapper.raildriver:create  (si 'create' devuelve el objeto)
REM Perfil de control (permite override por variable de entorno)
if not defined TSC_PROFILE set "TSC_PROFILE=profiles\BR146.json"
if not exist "%TSC_PROFILE%" (
  echo [tsc_real] Aviso: No existe "%TSC_PROFILE%". Usando profiles\BR146.json
  set "TSC_PROFILE=profiles\BR146.json"
)
@echo off
setlocal
title TSC – Real (GetData)
pushd "%~dp0\.."

if not exist ".venv\Scripts\activate.bat" (
  echo [!] No se encuentra .venv. Crea el entorno:  python -m venv .venv  &&  .venv\Scripts\activate && pip install -r requirements.txt
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"

rem === Ajusta esta ruta si tu GetData.txt esta en otro sitio ===
set "TSC_GETDATA_FILE=C:\Program Files (x86)\Steam\steamapps\common\RailWorks\plugins\GetData.txt"

set RUN_CSV=data\runs\run.csv
set EVENTS=data\events.jsonl
REM (No usar PROFILE, usar TSC_PROFILE)
set BUS=data\lua_eventbus.jsonl
rem salida única por ejecución (evita bloqueos de Excel/AV y colisiones)
set OUT=data\runs\ctrl_live_%RANDOM%.csv

if not exist "data\runs" mkdir "data\runs"
if not exist "data" mkdir "data"
del /q "%OUT%" 2>nul

start "TSC GetData Bridge" cmd /k "python -m ingestion.getdata_bridge"
timeout /t 2 >nul
start "TSC Collector" cmd /k "python -m runtime.collector --hz 10 --bus-from-start"
timeout /t 2 >nul
python -m tools.db_check --db data\run.db
start "TSC Control Loop" cmd /k "python -m runtime.control_loop --source sqlite --db data\run.db --bus %BUS% --events %EVENTS% --profile %TSC_PROFILE% --hz 5 --start-events-from-end --mode %TSC_MODE% --rd "%TSC_RD%" --emit-active-limit --out %OUT%"
start "Tail ctrl_live" powershell -NoLogo -NoProfile -Command "while(!(Test-Path '%OUT%')){Start-Sleep 0.5}; Get-Content '%OUT%' -Tail 10 -Wait"

popd
endlocal
