@echo off
call "%~dp0env\defaults.bat" || exit /b 1
call "%~dp0env\rd_provider.bat"
if not defined TSC_RD goto :no_rd
set "TSC_RD_DEBUG=1"
set "TSC_BRAKE_INVERT=1"
echo [oneclick_real_invert] mode=%TSC_MODE%  rd=%TSC_RD%  invert=1
call "%~dp0tsc_real.bat"
call "%~dp0tsc_report.bat"
pause
goto :eof
:no_rd
echo [oneclick_real_invert] ERROR: Define TSC_RD en scripts\env\rd_provider.bat o en el entorno y vuelve a ejecutar.
exit /b 1
