@echo off
setlocal EnableExtensions
REM ============================================
REM   tsc_kpi.bat – Detecta último CSV y valida
REM ============================================
set "CSV=%~1"

REM 0) Si nos pasan ruta por argumento y existe, usarla
if defined CSV (
  if exist "%CSV%" goto :after_find
  echo [tsc_kpi] CSV pasado por argumento no existe: %CSV%
  exit /b 1
)

REM 1) Buscar el CSV de control mas reciente en data\runs (desc), excluyendo *_events.csv y *_report*.csv
for /f "usebackq delims=" %%F in (`dir /b /a-d /o-d "data\runs\ctrl_live_*.csv" 2^>nul`) do (
  rem Excluir si el nombre contiene _events o _report
  echo %%~nF | findstr /I "_events _report" >nul
  if errorlevel 1 (
    set "CSV=data\runs\%%~nxF"
    goto :after_find
  )
)

REM 2) Fallback al clásico data\ctrl_live.csv
if exist "data\ctrl_live.csv" (
  set "CSV=data\ctrl_live.csv"
) else (
  echo [tsc_kpi] No se encontro CSV en data\runs\ctrl_live_*.csv ni data\ctrl_live.csv
  exit /b 1
)

:after_find
echo [tsc_kpi] CSV: %CSV%

REM Ejecutar validador (llamada directa al .py para no depender de paquete Python)
 python "tools\validate_kpi.py" --csv "%CSV%" ^
   --arrival-dist-m 8 ^
   --arrival-vmargin-kph 0.5 ^
   --window-m 50 ^
   --monotonicity-bump-m 2 ^
   --smooth-dist-window 3 ^
   --bump-confirm-samples 2 ^
   --dump-bumps "data\runs\kpi_bumps_latest.csv" ^
   --min-arrivals-ok 0.90

exit /b %errorlevel%
