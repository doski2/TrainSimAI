@echo off
call "%~dp0env\rd_provider.bat"
if not defined TSC_RD (
  echo [rd_test] ERROR: Define TSC_RD en scripts\env\rd_provider.bat
  exit /b 1
)
set "TSC_RD_DEBUG=1"
set "TSC_RD_LOG_RESET=1"
python -m tools.rd_smoketest --rd "%TSC_RD%" --pattern "0,0.3,0.6,0.9,0.0" --step-ms 700
pause
