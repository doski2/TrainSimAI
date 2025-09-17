@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM Ir al root del repo (este .bat vive en scripts\)
pushd "%~dp0\.."

REM ========= Defaults y entorno =========
if not defined TSC_MODE     set "TSC_MODE=brake"
if not defined TSC_PROFILE  set "TSC_PROFILE=profiles\BR146_ok4.json"
if not defined TSC_RD       set "TSC_RD="

REM Si el perfil no existe, fallback a profiles\BR146.json
if not exist "%TSC_PROFILE%" (
  echo [tsc_real] Aviso: No existe "%TSC_PROFILE%". Usando profiles\BR146.json
  set "TSC_PROFILE=profiles\BR146.json"
)

REM Si no hay RD definido, usa el stub (así siempre haya envío/log)
if not defined TSC_RD (
  set "TSC_RD=runtime.raildriver_stub:rd"
  if not defined TSC_RD_DEBUG set "TSC_RD_DEBUG=1"
  echo [tsc_real] AVISO: TSC_RD no definido. Usando stub.
)

REM ========= Preparar args dinámicos =========
REM Por defecto, seguimos desde el final del bus; si el usuario pasa --bus-from-start lo anulamos
set "BUS_TAIL=--start-events-from-end"
echo %* | findstr /I /C:"--bus-from-start" >nul && set "BUS_TAIL="

REM Asegurar carpetas de salida
if not exist "data\runs"  mkdir "data\runs"
if not exist "data\plots" mkdir "data\plots"

REM Nombre de salida con RANDOM para evitar colisiones
set "RUN_CSV=data\runs\ctrl_live_%RANDOM%.csv"

echo === tsc_real ==============================================
echo PROFILE : %TSC_PROFILE%
echo MODE    : %TSC_MODE%
echo RD      : %TSC_RD%
if defined TSC_RD_DEBUG (echo RD_DEBUG=1) else (echo RD_DEBUG=0)
echo BUS_TAIL: %BUS_TAIL%
echo OUT CSV : %RUN_CSV%
echo EXTRA   : %*
echo ============================================================

REM ========= Lanzar control loop =========
python -m runtime.control_loop ^
  --source sqlite --db data\run.db --bus data\lua_eventbus.jsonl ^
  --events data\events.jsonl --profile "%TSC_PROFILE%" --hz 5 %BUS_TAIL% ^
  --mode %TSC_MODE% --rd "%TSC_RD%" --emit-active-limit ^
  --out "%RUN_CSV%" %*

set "RC=%ERRORLEVEL%"
popd
endlocal & exit /b %RC%
