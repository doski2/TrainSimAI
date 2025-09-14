@echo off
setlocal
REM === Carga defaults (perfil/modo, reset de logs) ===
if exist "%~dp0env\defaults.bat" call "%~dp0env\defaults.bat"

REM === Proveedor RD (si lo tienes definido, lo usa; si no, sin problema) ===
if exist "%~dp0env\rd_provider.bat" call "%~dp0env\rd_provider.bat"

echo [go] profile=%TSC_PROFILE%
echo [go] mode=%TSC_MODE%
if defined TSC_RD echo [go] rd=%TSC_RD%

call "%~dp0tsc_real.bat" || exit /b 1
call "%~dp0tsc_report.bat"
pause
endlocal
