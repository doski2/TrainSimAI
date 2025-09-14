@echo off
call "%~dp0env\defaults.bat" || exit /b 1
call "%~dp0env\rd_provider.bat"
if not defined TSC_RD (
  echo [oneclick_real] ERROR: Define TSC_RD en scripts\env\rd_provider.bat (o en el entorno) y vuelve a ejecutar.
  exit /b 1
)
REM Debug inicialmente ON para ver rd_send.log; desactiva poniendo 0 si molesta
set set "TSC_RD=ingestion.rd_client:rd"
echo [oneclick_real] mode=%TSC_MODE%  rd=%TSC_RD%
call "%~dp0tsc_real.bat"
call "%~dp0tsc_report.bat"
pause
