@echo off
setlocal
pushd "%~dp0\.."
set OUT=data\ctrl_live.csv
powershell -NoLogo -NoProfile -Command "while(!(Test-Path '%OUT%')){Start-Sleep 0.5}; Get-Content '%OUT%' -Tail 20 -Wait"
popd
endlocal
