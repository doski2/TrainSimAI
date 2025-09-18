@echo off
setlocal
@echo off
setlocal
rem Ejecuta SOLO pruebas reales/integración. Activa RailDriver live.
set RUN_RD_TESTS=1
pushd %~dp0\..
set RUN_RD_TESTS=1
pytest -q -m "real"
popd
