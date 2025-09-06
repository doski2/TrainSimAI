## TrainSimAI
Telemetría y eventos para Train Simulator Classic usando py-raildriver (controles/cabina) y LUA (límites, paradas, marcadores).

Genera:
- `data/runs/*.csv` (~9–10 Hz): velocidad, frenos, SIFA/PZB/LZB/AFB, lat/lon/heading/gradient, hora in‑game, `odom_m`.
- `data/events/events.jsonl`: eventos normalizados (`marker_pass`, `speed_limit_change`, `stop_begin/stop_end`, ...).

### Requisitos
- Windows + Python 3.11+
- Train Simulator Classic instalado
- Drivers RailDriver / DLL accesible

### Instalación
```powershell
pip install -r requirements.txt
```

### Configurar el bus LUA
1) Abre `lua/tsc_eventbus.lua` y fija ruta absoluta del repo:
```lua
-- usa / en vez de \
local EVENTBUS_PATH = "C:/RUTA/A/Tu/Repo/data/lua_eventbus.jsonl"
```
2) En PowerShell (raíz del repo) exporta la misma ruta para el collector:
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

### Validar
```powershell
python tools/validate_run.py
```
Salida esperada:
- Hz ≈ 9–10
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
/lua          # scripts LUA (eventos de límite, paradas, marcadores)
/profiles     # mapeos por locomotora (controles y rangos)
/tools        # utilidades (validador, caps, repair)
/data         # runs/*.csv y events/*.jsonl
```

### Solución de problemas
- No aparece `events.jsonl`: alinea `EVENTBUS_PATH` y `LUA_BUS_PATH`; crea los archivos vacíos; fuerza un evento:
  ```powershell
  Add-Content .\data\lua_eventbus.jsonl -Value '{"type":"marker_pass","name":"manual","time":1}'
  ```
- Eventos duplicados o sin lat/lon: asegura un solo escritor de eventos (solo el collector).
- Hz ≤ 5: asegúrate de usar la versión reciente del Lua EventBus (sin sleeps innecesarios cuando falta el archivo).
- CSV "field larger than field limit": usa `tools/repair_csv.py` y la versión nueva de `runtime/csv_logger.py`.
- Ver capacidades de la DLL: `python tools/rd_caps.py`.

### Roadmap corto
- `speed_limit_change` + distancia (LUA)
- Paradas con nombre (marcadores de andén)
- Validación de frenado/AFB (gráficas con `odom_m`)

### Licencia
MIT

