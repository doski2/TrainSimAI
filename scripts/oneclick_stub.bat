@echo off
call "%~dp0env\defaults.bat" || exit /b 1
REM Forzamos RD stub + debug para ver envio de freno y crear rd_send.log
set "TSC_RD=runtime.raildriver_stub:rd"
set "TSC_RD_DEBUG=1"
echo [oneclick_stub] mode=%TSC_MODE%  rd=%TSC_RD%
call "%~dp0tsc_real.bat"
call "%~dp0tsc_report.bat"
pause
