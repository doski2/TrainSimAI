@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM Ir al root del repo (este .bat vive en scripts\)
pushd "%~dp0\.."

REM ====== Asegurar carpetas/paths ======
if not exist "data\runs"  mkdir "data\runs"
if not exist "data\plots" mkdir "data\plots"
set "KPI_TXT=data\kpi_latest.txt"

REM ====== Elegir CSV (último ctrl_live_*.csv; excluye *_events/_report) ======
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
  popd
  endlocal & exit /b 1
)
:csv_ok
echo [tsc_report] CSV = %CSV%

REM ====== Generar report (intenta API nueva --in; fallback a --csv) ======
call :run_report "%CSV%"
if errorlevel 1 (
  echo [tsc_report] ERROR: session_report fallo.
  popd
  endlocal & exit /b 2
)

REM ====== Asegurar KPI file ======
if not exist "%KPI_TXT%" (
  echo arrivals_ok=0.000> "%KPI_TXT%"
  echo monotonicity_bumps=999>> "%KPI_TXT%"
  echo mean_margin_last50_kph=9.999>> "%KPI_TXT%"
)

REM ====== Leer KPI y aplicar gate ======
for /f "tokens=1,2 delims== " %%A in (%KPI_TXT%) do (
  if /I "%%A"=="arrivals_ok" set "ARR_OK=%%B"
  if /I "%%A"=="monotonicity_bumps" set "BUMPS=%%B"
  if /I "%%A"=="mean_margin_last50_kph" set "MARG=%%B"
)
if not defined ARR_OK set "ARR_OK=0"
if not defined BUMPS set "BUMPS=999"
if not defined MARG set "MARG=9.999"
echo [tsc_report] KPI -> arrivals_ok=%ARR_OK%  bumps=%BUMPS%  mean_margin_last50_kph=%MARG%

REM Verde si: arrivals_ok>=0.90 y bumps==0 y 0.3<=MARG<=1.5
set "KPI_GREEN=0"
for /f "usebackq" %%Z in (`powershell -NoProfile -Command ^
  "( [double]'%ARR_OK%' -ge 0.90 ) -and ( [int]'%BUMPS%' -eq 0 ) -and ( [double]'%MARG%' -ge 0.3 ) -and ( [double]'%MARG%' -le 1.5 )"`) do (
  if /I "%%Z"=="True" set "KPI_GREEN=1"
)

if "%KPI_GREEN%"=="1" (
  echo [tsc_report] KPI gate OK
) else (
  echo [tsc_report] KPI gate FAIL
  popd
  endlocal & exit /b 3
)

REM ====== Auto-tune conservador (solo con KPI verde y perfil existente) ======
if defined TSC_PROFILE if exist "%TSC_PROFILE%" (
  echo [tsc_report] AUTOTUNE sobre %TSC_PROFILE%
  python tools\autotune_profile.py --profile "%TSC_PROFILE%" --kpi-file "%KPI_TXT%" --target 0.8 --step 0.5
) else (
  echo [tsc_report] Skip autotune (TSC_PROFILE no definido o no existe)
)

popd
endlocal & exit /b 0

:run_report
REM intenta interfaz nueva (--in); si falla, interfaz antigua (--csv)
python tools\session_report.py --in "%~1"
if "%errorlevel%"=="0" exit /b 0
python tools\session_report.py --csv "%~1"
exit /b %errorlevel%
