@echo off
setlocal
pushd "%~dp0\.."
call .venv\Scripts\activate.bat 2>nul || (echo [!] Falta .venv && exit /b 1)

python -m tools.db_check --db data\run.db
if exist data\runs\run.csv (
  echo [runs] existe data\runs\run.csv
  powershell -NoLogo -NoProfile -Command "Get-Content 'data\runs\run.csv' -Tail 3"
) else (
  echo [runs] NO existe data\runs\run.csv
)

popd
endlocal
