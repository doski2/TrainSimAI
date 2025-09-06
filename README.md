# TrainSimAI — Colector de telemetría y eventos para TS Classic

Herramientas para registrar telemetría (py‑raildriver) y eventos (bridge LUA) en TS Classic: CSV continuo y JSONL de eventos (límites, paradas, marcadores).

**Estado rápido**
- Python 3.10+ en Windows.
- Escribe `data/runs/run.csv` y `data/events/events.jsonl`.
- Eventos desde LUA via `data/lua_eventbus.jsonl`.

**Instalación**
- Requisitos: Python 3.10+ (recomendado 3.11).
- Instala dependencias:
  - `pip install -r requirements.txt`
  - Opcional entorno virtual: `python -m venv .venv && .venv\Scripts\activate`

**Lanzar el colector**
- Modo módulo: `python -m runtime.collector`
- O directo: `python runtime/collector.py`
- Archivos de salida:
  - `data/runs/run.csv`: telemetría a ~10–12 Hz.
  - `data/events/events.jsonl`: eventos normalizados.

**Variables de entorno (opcionales)**
- `LUA_BUS_PATH`: ruta al bus JSONL que escribe el script LUA. Por defecto `data/lua_eventbus.jsonl`.
- `RUN_CSV_PATH`: ruta de salida del CSV (por defecto `data/runs/run.csv`).
- `RUN_EVT_PATH`: ruta de salida de eventos (por defecto `data/events/events.jsonl`).
- `RUN_HB_PATH`: fichero heartbeat para exclusión mutua (por defecto `data/events/.collector_heartbeat`).

**Integración LUA (próximos límites y marcadores/andén)**
- Copia o referencia `lua/tsc_eventbus.lua` como Script de Escenario en TS Classic.
  - IMPORTANTE: `EVENTBUS_PATH` en el LUA debe ser la MISMA ruta que usa el colector (`LUA_BUS_PATH`).
  - Ejemplo recomendado (Windows, barras /): `C:/TrainSimAI/data/lua_eventbus.jsonl`.
  - Puedes dejar el colector con el valor por defecto (`data/lua_eventbus.jsonl`) o forzar la misma ruta con:
    - PowerShell: ``$env:LUA_BUS_PATH = "C:/TrainSimAI/data/lua_eventbus.jsonl"``
    - CMD: ``set LUA_BUS_PATH=C:/TrainSimAI/data/lua_eventbus.jsonl``
- Para marcar andenes con nombre, usa un marcador con el script `lua/platform_marker.lua` y ajusta `STATION_NAME`.
- El colector fusiona telemetría y eventos del bus LUA y solo escribe eventos enriquecidos (con lat/lon cuando apliquen).

**Rutas del bus LUA (importante)**
- No mezcles rutas distintas (p. ej., `C:/Users/Public/Documents/...` vs `data/lua_eventbus.jsonl`).
- Deben coincidir: lo que escribe el LUA (`EVENTBUS_PATH`) = lo que lee el colector (`LUA_BUS_PATH`).
- Usa rutas absolutas en el LUA con barras `/` para evitar problemas de escape.

**Validación rápida**
- Ejecuta: `python tools/validate_run.py`
- Ejemplo de salida esperada:
```
[CSV] Filas: 6000+ | Columnas: 60+
[CSV] Loco más frecuente: DB BR146.0 (... filas)
[CSV] Tasa de muestreo ~ 9–12 Hz en últimas N filas
[EVT] Total eventos: ... | Por tipo: {'speed_limit_change': X, 'marker_pass': Y, ...}
```

**Solución de problemas**
- Duplicados en `events.jsonl`: asegúrate de NO ejecutar `tools/drain_lua_bus.py` cuando esté activo el colector. El colector crea `data/events/.collector_heartbeat`; el drain moderno se autoinhibe si detecta heartbeat.
- Sin coordenadas en eventos de marcador: el colector filtra eventos sin lat/lon; verifica que el CSV tenga `!Coordinates` y que el LUA emita el evento mientras el colector está activo.

**Rotación de runs (offline fácil)**
- Antes de iniciar una sesión nueva, rota el CSV anterior:
  - Python: `python tools/rotate_runs.py` (usa `RUN_CSV_PATH` si lo tienes personalizado)
  - Encadenado: `python tools/rotate_runs.py && python -m runtime.collector`
  - También puedes pasar la ruta: `python tools/rotate_runs.py data/runs/run.csv`
  - Resultado: `data/runs/run_YYYYMMDD_HHMMSS.csv`

**Licencia y crédito**
- Licencia: MIT (ver `LICENSE`).
- Basado en `py-raildriver` para lectura de cabina. Este repositorio no incluye contenido de DTG/TS Classic.

**About del repositorio (GitHub)**
- Descripción sugerida: “Telemetría y eventos para Train Simulator Classic (py‑raildriver + LUA), con colector a CSV/JSONL y herramientas de validación.”
- Topics sugeridos: `train-simulator`, `raildriver`, `lua`, `autopilot`, `telemetry`, `python`.
- Configúralos en GitHub: Settings → General → “Description” y “Topics”.
