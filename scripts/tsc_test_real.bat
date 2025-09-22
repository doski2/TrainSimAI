@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM ================================================================
REM  TSC RD-REAL TEST RUNNER (zip al terminar)
REM
REM  Uso:
REM    scripts\tsc_test_real.bat --rd-impl paquete.modulo:objeto ^
REM       [--profile profiles\BR146_ok4.json] ^
REM       [--duration SEG] [--bus-from-start] [--debug|--no-debug]
REM ================================================================

REM --------- Valores por defecto (ajústalos si quieres) ----------
set "PROFILE=profiles\BR146_ok4.json"
set "MODE=brake"
set "RD=ingestion.rd_client:rd"
set "RD_IMPL="
set "DEBUG=1"
set "LOG_RESET=1"
set "DURATION="
set "BUS_FROM_START="

REM -------------------- Parseo de flags ---------------------------
:parse
if "%~1"=="" goto ready
if /I "%~1"=="--help"            goto help
if /I "%~1"=="--rd-impl"         set "RD_IMPL=%~2" & shift & shift & goto parse
if /I "%~1"=="--profile"         set "PROFILE=%~2" & shift & shift & goto parse
if /I "%~1"=="--duration"        set "DURATION=%~2" & shift & shift & goto parse
if /I "%~1"=="--bus-from-start"  set "BUS_FROM_START=1" & shift & goto parse
if /I "%~1"=="--debug"           set "DEBUG=1" & shift & goto parse
if /I "%~1"=="--no-debug"        set "DEBUG="  & shift & goto parse
echo [WARN] Opcion desconocida: %1
shift
goto parse

:ready
if not defined RD_IMPL (
  echo [ERROR] Debes indicar --rd-impl paquete.modulo:objeto_o_factory
  goto help
)

REM -------------------- Exportar entorno --------------------------
set "TSC_PROFILE=%PROFILE%"
set "TSC_MODE=%MODE%"
set "TSC_RD=%RD%"
set "TSC_RD_IMPL=%RD_IMPL%"
set "TSC_FAKE_RD="
if defined DEBUG (
  set "TSC_RD_DEBUG=1"
) else (
  set "TSC_RD_DEBUG="
)
if defined LOG_RESET (
  set "TSC_RD_LOG_RESET=1"
) else (
  set "TSC_RD_LOG_RESET="
)

REM -------------------- Extra args al runner ----------------------
set "EXTRA_ARGS="
if defined DURATION       set "EXTRA_ARGS=!EXTRA_ARGS! --duration !DURATION!"
if defined BUS_FROM_START set "EXTRA_ARGS=!EXTRA_ARGS! --bus-from-start"

echo.
echo === TSC RD-REAL TEST ========================================
echo PROFILE : %TSC_PROFILE%
echo MODE    : %TSC_MODE%
echo RD      : %TSC_RD%
echo RD_IMPL : %TSC_RD_IMPL%
if defined TSC_RD_DEBUG   (echo RD_DEBUG=1) else (echo RD_DEBUG=0)
if defined TSC_RD_LOG_RESET (echo RD_LOG_RESET=1) else (echo RD_LOG_RESET=0)
echo EXTRA   : !EXTRA_ARGS!
echo ==============================================================
echo.

REM Reset del log de RD si procede
if defined TSC_RD_LOG_RESET if exist ".\data\rd_send.log" del /q ".\data\rd_send.log"

REM -------------------- Ejecutar RUN + REPORT ---------------------
call scripts\tsc_real.bat %EXTRA_ARGS%
set "RUN_EXIT=%ERRORLEVEL%"
call scripts\tsc_report.bat

REM -------------------- Empaquetar LOGS en ZIP -------------------
REM  Incluye: data\*.log, *.txt, *.csv, events\*.jsonl, runs\*.csv, plots\*.png
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$stamp=Get-Date -Format 'yyyyMMdd_HHmmss';" ^
  "$out='out'; if(!(Test-Path $out)){New-Item -ItemType Directory -Path $out|Out-Null};" ^
  "$zip=Join-Path $out ('tsc_logs_'+$stamp+'.zip');" ^
  "$patterns=@('data\*.log','data\*.txt','data\*.csv','data\events\*.jsonl','data\runs\*.csv','data\plots\*.png');" ^
  "$items=@(); foreach($p in $patterns){ $items+=Get-ChildItem -Path $p -ErrorAction SilentlyContinue };" ^
  "if($items.Count -gt 0){ Compress-Archive -Path $items.FullName -DestinationPath $zip -Force; Write-Host ('ZIP: '+$zip) } else { Write-Host 'ZIP: (sin archivos que comprimir)'}"

exit /b %RUN_EXIT%

:help
echo Uso:
echo   scripts\tsc_test_real.bat --rd-impl paquete.modulo:objeto_o_factory ^
echo       [--profile profiles\BR146_ok4.json] [--duration SEG] [--bus-from-start] [--debug ^| --no-debug]
exit /b 2
