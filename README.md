## TrainSimAI
TelemetrÃ­a y eventos para Train Simulator Classic usando py-raildriver (controles/cabina) y LUA (lÃ­mites, paradas, marcadores).

Genera:
- `data/runs/*.csv` (~9â€“10 Hz): velocidad, frenos, SIFA/PZB/LZB/AFB, lat/lon/heading/gradient, hora inâ€‘game, `odom_m`.
- `data/events/events.jsonl`: eventos normalizados (`marker_pass`, `speed_limit_change`, `stop_begin/stop_end`, ...).

### Requisitos
- Windows + Python 3.11+
- Train Simulator Classic instalado
- Drivers RailDriver / DLL accesible

Nota de arquitectura: la DLL debe coincidir con la arquitectura de tu Python.
- Python 64‑bit → usa `RailDriver64.dll`
- Python 32‑bit → usa `RailDriver.dll`
Si mezclas (p. ej., Python 64 con DLL 32), verás errores tipo WinError 193.

### InstalaciÃ³n
```powershell
pip install -r requirements.txt
```

### Configurar el bus LUA
1) Abre `lua/tsc_eventbus.lua` y fija ruta absoluta del repo:
```lua
-- usa / en vez de \
local EVENTBUS_PATH = "C:/RUTA/A/Tu/Repo/data/lua_eventbus.jsonl"
```
2) En PowerShell (raÃ­z del repo) exporta la misma ruta para el collector:
```powershell
$env:LUA_BUS_PATH = (Join-Path $PWD 'data\lua_eventbus.jsonl')
```
3) Crea las carpetas/archivos:
```powershell
New-Item -ItemType Directory -Force -Path .\data,.\data\events | Out-Null
New-Item -ItemType File -Force -Path .\data\lua_eventbus.jsonl,.\data\events\events.jsonl | Out-Null
```

### Ejecutar el collector
```powershell
python -m runtime.collector    # o: python .\runtime\collector.py
```
Importante: deja solo este proceso escribiendo `events.jsonl` (no ejecutes `tools/drain_lua_bus.py` en paralelo).

Por defecto, el collector lee el bus en modo â€œtailâ€ (solo lÃ­neas nuevas). Para pruebas cortas puedes limitar duraciÃ³n y fijar Hz objetivo:
```powershell
python -m runtime.collector --duration 5 --hz 12
```

Reprocesar histÃ³rico (leer el bus desde el inicio):
```powershell
python -m runtime.collector --bus-from-start --duration 5
```
Ãšsalo cuando ya tengas eventos previos escritos en `data/lua_eventbus.jsonl` antes de arrancar el collector.
# Reprocesar todo el bus (histórico):
```
python -m runtime.collector --bus-from-start
```

Reprocesar histórico del bus (si escribiste antes de arrancar):
python -m runtime.collector --bus-from-start

### Validar
```powershell
python tools/validate_run.py
```
Salida esperada:
- Hz â‰ˆ 9â€“10
- Loco detectada (p. ej. DB BR146.0)
- Sin avisos por Throttle/MPH si tienes Regulator/KPH

### Rotar runs (opcional)
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\rotate-run.ps1
```

### Estructura
```
/ingestion    # py-raildriver wrapper, bus LUA
/runtime      # collector, csv logger, normalizador eventos
/lua          # scripts LUA (eventos de lÃ­mite, paradas, marcadores)
/profiles     # mapeos por locomotora (controles y rangos)
/tools        # utilidades (validador, caps, repair)
/data         # runs/*.csv y events/*.jsonl
```

### Solución de problemas
- No aparece `events.jsonl`: alinea `EVENTBUS_PATH` y `LUA_BUS_PATH`; crea los archivos vacÃ­os; fuerza un evento:
  ```powershell
  Add-Content .\data\lua_eventbus.jsonl -Value '{"type":"marker_pass","name":"manual","time":1}'
  ```
- Eventos duplicados o sin lat/lon: asegura un solo escritor de eventos (solo el collector).
- Hz â‰¤ 5: asegÃºrate de usar la versiÃ³n reciente del Lua EventBus (sin sleeps innecesarios cuando falta el archivo).
- CSV "field larger than field limit": usa `tools/repair_csv.py` y la versión nueva de `runtime/csv_logger.py`.
- Ver capacidades de la DLL: `python tools/rd_caps.py`.
 - Eventos previos al arranque no aparecen → usa `--bus-from-start`.
 - Evita doble escritor: collector OR drain, no ambos a la vez.
 - Si inyectas en el bus antes de arrancar el collector, usa `--bus-from-start`.
 - No ejecutes `tools/drain_lua_bus.py` a la vez que el collector (evita duplicados).

### Modo simulado (sin hardware)

Para desarrollar y ejecutar sin la DLL de RailDriver ni hardware conectado:

- Fuerza el backend simulado exportando `TSC_FAKE_RD=1`.

PowerShell (Windows):
```powershell
$env:TSC_FAKE_RD = '1'
python -m runtime.collector --duration 5 --hz 12
pytest -q
```

Bash (Linux/macOS):
```bash
export TSC_FAKE_RD=1
python -m runtime.collector --duration 5 --hz 12
pytest -q
```

Tests:
- Las pruebas que dependen de la DLL real se marcan como skipped por defecto.
- Para forzar su ejecución (si tienes la DLL y hardware): define `RUN_RD_TESTS=1` antes de `pytest`.

CI:
- El workflow de GitHub Actions ejecuta con `TSC_FAKE_RD=1` y corre linters + pytest con cobertura.

### Roadmap corto
- `speed_limit_change` + distancia (LUA)
- Paradas con nombre (marcadores de andÃ©n)
- ValidaciÃ³n de frenado/AFB (grÃ¡ficas con `odom_m`)

### Licencia
MIT



### RailDriver (DLL)
- Python x64 → `RailDriver64.dll` | Python x86 → `RailDriver.dll`.
- Variables soportadas:
  - `TSC_RD_DLL_DIR`: carpeta que contiene la DLL.
  - `RAILWORKS_PLUGINS`: carpeta `...\RailWorks\plugins`.
- Si aparece WinError 193, revisa la arquitectura de Python y la DLL cargada. El collector imprime la DLL elegida al iniciar (`[rd] usando DLL: ...`).
