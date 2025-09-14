@echo off
setlocal
REM ===== elegir ultimo ctrl_live_*.csv (no events/report) =====
set "CSV="
for /f "usebackq delims=" %%F in (`dir /b /a-d /o-d "data\runs\ctrl_live_*.csv" 2^>nul`) do (
  echo %%~nF | findstr /I "_events _report" >nul
  if errorlevel 1 (
    set "CSV=data\runs\%%~nxF"
    goto :csv_ok
  )
)
if not defined CSV if exist "data\ctrl_live.csv" set "CSV=data\ctrl_live.csv"
if not defined CSV (
  echo [tsc_report] ERROR: No hay ctrl_live CSV.
  exit /b 1
)
:csv_ok

echo [tsc_report] Analizando "%CD%\%CSV%"

REM ===== ejecutar session_report (soporta --in o --csv) =====
call :run_report "%CSV%"
if errorlevel 1 (
  echo [tsc_report] ERROR: session_report.py fallo.
  exit /b 1
)
echo [tsc_report] Hecho.

REM ===== KPI gate (despues del informe) =====
call "%~dp0tsc_kpi.bat" "%CSV%"
set "KPI_RC=%errorlevel%"
if "%KPI_RC%"=="0" goto :kpi_ok
echo [tsc_report] KPI gate FAILED (rc=%KPI_RC%). Revisa arriba.
exit /b %KPI_RC%
:kpi_ok
echo [tsc_report] KPI gate OK

endlocal
exit /b 0

:run_report
REM intenta interfaz nueva (--in); si falla, interfaz antigua (--csv)
python tools\session_report.py --in "%~1"
if "%errorlevel%"=="0" exit /b 0
python tools\session_report.py --csv "%~1"
exit /b %errorlevel%
