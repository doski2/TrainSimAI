@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM ==================================================================
REM  TSC unified test (RD real o stub) + ZIP automático al finalizar
REM ==================================================================
REM Uso:
REM   scripts\tsc_test.bat ^
REM     [--rd-impl paquete.modulo:objeto] [--save-rd-impl] ^
REM     [--profile profiles\BR146_ok4.json] [--mode brake|auto] ^
REM     [--duration SEG] [--bus-from-start] [--debug|--no-debug]
REM ==================================================================

REM Ir al root del repo (este .bat vive en scripts\)
pushd "%~dp0\.."

REM ---- Defaults -----------------------------------------------------
set "PROFILE=profiles\BR146_ok4.json"
set "MODE=brake"
set "RD=ingestion.rd_client:rd"
set "RD_IMPL="
set "DEBUG=1"
set "LOG_RESET=1"
set "DURATION="
set "BUS_FROM_START="
set "SAVE_RD_IMPL="

REM ---- Parseo de flags ---------------------------------------------
:parse
if "%~1"=="" goto ready
if /I "%~1"=="--help"           goto help
if /I "%~1"=="--profile"        set "PROFILE=%~2" & shift & shift & goto parse
if /I "%~1"=="--mode"           set "MODE=%~2" & shift & shift & goto parse
if /I "%~1"=="--rd-impl"        set "RD_IMPL=%~2" & shift & shift & goto parse
if /I "%~1"=="--save-rd-impl"   set "SAVE_RD_IMPL=1" & shift & goto parse
if /I "%~1"=="--duration"       set "DURATION=%~2" & shift & shift & goto parse
if /I "%~1"=="--bus-from-start" set "BUS_FROM_START=1" & shift & goto parse
if /I "%~1"=="--debug"          set "DEBUG=1" & shift & goto parse
if /I "%~1"=="--no-debug"       set "DEBUG="  & shift & goto parse
echo [WARN] Opcion desconocida: %1
shift
goto parse

:ready
set "RD_IMPL_RES=%RD_IMPL%"
if not defined RD_IMPL_RES (
	if exist "scripts\rd_impl.txt" (
		for /f "usebackq delims=" %%R in ("scripts\rd_impl.txt") do set "RD_IMPL_RES=%%R"
	)
)
if not defined RD_IMPL_RES (
	if defined TSC_RD_IMPL (
		set "RD_IMPL_RES=%TSC_RD_IMPL%"
	)
)

REM ---- Exportar entorno --------------------------------------------
set "TSC_PROFILE=%PROFILE%"
set "TSC_MODE=%MODE%"
set "TSC_RD=%RD%"
if defined RD_IMPL_RES (
	set "TSC_RD_IMPL=%RD_IMPL_RES%"
	set "TSC_FAKE_RD="
) else (
	set "TSC_RD_IMPL="
	set "TSC_FAKE_RD=1"
)
if defined DEBUG (
	set "TSC_RD_DEBUG=1"
) else (
	set "TSC_RD_DEBUG="
)
if defined LOG_RESET (
	set "TSC_RD_LOG_RESET=1"
) else (
	set "TSC_RD_LOG_RESET="
)

REM ---- Extra args para el runner -----------------------------------
set "EXTRA_ARGS="
if defined DURATION       set "EXTRA_ARGS=!EXTRA_ARGS! --duration !DURATION!"
if defined BUS_FROM_START set "EXTRA_ARGS=!EXTRA_ARGS! --bus-from-start"

echo.
echo === TSC TEST (unificado) =======================================
echo PROFILE : %TSC_PROFILE%
echo MODE    : %TSC_MODE%
echo RD      : %TSC_RD%
if defined TSC_RD_IMPL (
	echo RD_IMPL: %TSC_RD_IMPL%
) else (
	echo RD_IMPL: ^(none^)  [usando STUB]
)
if defined TSC_RD_DEBUG   (echo RD_DEBUG=1) else (echo RD_DEBUG=0)
if defined TSC_RD_LOG_RESET (echo RD_LOG_RESET=1) else (echo RD_LOG_RESET=0)
echo EXTRA   : !EXTRA_ARGS!
echo ================================================================
echo.

REM ---- Validar import del RD_IMPL (si existe) ----------------------
if defined TSC_RD_IMPL (
	for /f "tokens=1,2 delims=:" %%A in ("%TSC_RD_IMPL%") do (
		set "RD_MOD=%%A"
		set "RD_OBJ=%%B"
	)
	python -c "import importlib,traceback,sys; m=importlib.import_module(r'%RD_MOD%'); getattr(m,r'%RD_OBJ%'); print('RD_IMPL_OK')"
	if errorlevel 1 (
		echo [ERROR] No puedo importar %TSC_RD_IMPL%
		echo ---- Traceback arriba ----
		popd
		exit /b 2
	)
	if defined SAVE_RD_IMPL (
		> "scripts\rd_impl.txt" echo %TSC_RD_IMPL%
	)
)

REM ---- Reset del log RD si procede ---------------------------------
if defined TSC_RD_LOG_RESET if exist ".\data\rd_send.log" del /q ".\data\rd_send.log"

REM ---- Ejecutar run + report ---------------------------------------
call scripts\tsc_real.bat %EXTRA_ARGS%
set "RUN_EXIT=%ERRORLEVEL%"
call scripts\tsc_report.bat

REM ---- Empaquetar logs a ZIP --------------------------------------
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
	"$stamp=Get-Date -Format 'yyyyMMdd_HHmmss';" ^
	"$out='out'; if(!(Test-Path $out)){New-Item -ItemType Directory -Path $out|Out-Null};" ^
	"$zip=Join-Path $out ('tsc_logs_'+$stamp+'.zip');" ^
	"$patterns=@('data\*.log','data\*.txt','data\*.csv','data\events\*.jsonl','data\runs\*.csv','data\plots\*.png');" ^
	"$items=@(); foreach($p in $patterns){ $items+=Get-ChildItem -Path $p -ErrorAction SilentlyContinue };" ^
	"if($items.Count -gt 0){ Compress-Archive -Path $items.FullName -DestinationPath $zip -Force; Write-Host ('ZIP: '+$zip) } else { Write-Host 'ZIP: (sin archivos que comprimir)'}"

popd
exit /b %RUN_EXIT%

:help
echo Uso:
echo   scripts\tsc_test.bat [opciones]
echo     --rd-impl pkg.mod:obj      Usa RD real (si falla import, aborta)
echo     --save-rd-impl             Guarda el valor en scripts\rd_impl.txt
echo     --profile RUTA\perfil.json Perfil (por defecto %PROFILE%)
echo     --mode brake^|auto           Modo (default %MODE%)
echo     --duration SEG             Limita duracion del run
echo     --bus-from-start          Lee el bus desde el inicio
echo     --debug ^| --no-debug        Activa/desactiva rd_send.log
exit /b 0
		"$items=@(); foreach($p in $patterns){ $items+=Get-ChildItem -Path $p -ErrorAction SilentlyContinue };" ^
		"if($items.Count -gt 0){ Compress-Archive -Path $items.FullName -DestinationPath $zip -Force; Write-Host ('ZIP: '+$zip) } else { Write-Host 'ZIP: (sin archivos que comprimir)'}"

	popd
	exit /b %RUN_EXIT%

	:help
	echo Uso:
	echo   scripts\tsc_test.bat [opciones]
	echo     --rd-impl pkg.mod:obj      Usa RD real (si falla import, aborta)
	echo     --save-rd-impl             Guarda el valor en scripts\rd_impl.txt
	echo     --profile RUTA\perfil.json Perfil (por defecto %PROFILE%)
	echo     --mode brake^|auto           Modo (default %MODE%)
	echo     --duration SEG             Limita duracion del run
	echo     --bus-from-start          Lee el bus desde el inicio
	echo     --debug ^| --no-debug        Activa/desactiva rd_send.log
	exit /b 0

REM ---- Ejecutar run + report ---------------------------------------
call scripts\tsc_real.bat %EXTRA_ARGS%
set "RUN_EXIT=%ERRORLEVEL%"
call scripts\tsc_report.bat

REM ---- Empaquetar logs a ZIP --------------------------------------
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
	"$stamp=Get-Date -Format 'yyyyMMdd_HHmmss';" ^
	"$out='out'; if(!(Test-Path $out)){New-Item -ItemType Directory -Path $out|Out-Null};" ^
	"$zip=Join-Path $out ('tsc_logs_'+$stamp+'.zip');" ^
	"$patterns=@('data\*.log','data\*.txt','data\*.csv','data\events\*.jsonl','data\runs\*.csv','data\plots\*.png');" ^
	"$items=@(); foreach($p in $patterns){ $items+=Get-ChildItem -Path $p -ErrorAction SilentlyContinue };" ^
	"if($items.Count -gt 0){ Compress-Archive -Path $items.FullName -DestinationPath $zip -Force; Write-Host ('ZIP: '+$zip) } else { Write-Host 'ZIP: (sin archivos que comprimir)'}"

popd
exit /b %RUN_EXIT%

:help
echo Uso:
echo   scripts\tsc_test.bat [opciones]
echo     --rd-impl pkg.mod:obj      Usa RD real (si falla import, aborta)
echo     --save-rd-impl             Guarda el valor en scripts\rd_impl.txt
echo     --profile RUTA\perfil.json Perfil (por defecto %PROFILE%)
echo     --mode brake^|auto           Modo (default %MODE%)
echo     --duration SEG             Limita duracion del run
echo     --bus-from-start          Lee el bus desde el inicio
echo     --debug ^| --no-debug        Activa/desactiva rd_send.log
exit /b 0