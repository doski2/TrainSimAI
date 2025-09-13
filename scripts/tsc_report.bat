@echo off
setlocal enabledelayedexpansion
call ".venv\Scripts\activate.bat"
for /f "delims=" %%F in ('powershell -NoProfile -Command ^
  "(Get-ChildItem -Path 'data\\runs\\ctrl_live_*.csv' | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName"') do set "LAST=%%F"
if "%LAST%"=="" (
  echo [tsc_report] No se encontro ctrl_live_*.csv en data\runs
  exit /b 1
)
echo [tsc_report] Analizando %LAST%
python -m tools.session_report --in "%LAST%"
echo [tsc_report] Hecho.
REM ================================
REM KPI gate (despues del informe)
REM ================================
call "%~dp0tsc_kpi.bat"
set "KPI_RC=%errorlevel%"
if not "%KPI_RC%"=="0" (
  echo [tsc_report] KPI gate FAILED (rc=%KPI_RC%). Revisa arriba.
  exit /b %KPI_RC%
) else (
  echo [tsc_report] KPI gate OK.
)
endlocal
