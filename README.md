# TrainSimAI (TSC)

Autopiloto/analizador para **Train Simulator Classic** (Windows, Python 64-bit).
Pipeline: **GetData → Bus LUA → Collector → Distancia próximo límite → Frenada v0 (offline/online)** con trazas y tests.

## TL;DR (rápido)

```powershell
# 0) Entorno
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 1) Bridge (GetData → bus)
$env:TSC_GETDATA_FILE="C:\\Program Files (x86)\\Steam\\steamapps\\common\\RailWorks\\plugins\\GetData.txt"
python -m ingestion.getdata_bridge

# 2) Collector (normaliza y sella t_wall/odom)
python -m runtime.collector --hz 10 --bus-from-start

# 3) Distancia al próximo límite
python -m tools.dist_next_limit

# 4) Frenada v0 (offline → target_speed_kph, phase)
python -m tools.apply_frenada_v0 --log data/run.csv --dist data/run.dist.csv --events data/events.jsonl --out data/run.ctrl.csv --A 0.7 --margin-kph 3 --reaction 0.6

# 5) Plot
python -m tools.plot_run data/run.ctrl.csv
```

> Consulta **/docs** para detalles y fundamentos.

## Estructura
```
ingestion/   # Bridges y captura (GetData → bus LUA)
runtime/     # Collector y lógica online (PID/frenada en módulos dedicados)
tools/       # Utilidades offline (distancias, merge, plot)
tests/       # Unitarios/integ.
docs/        # Documentación (frenada v0, limpieza, guías)
profiles/    # (Opcional) perfiles por locomotora (A, márgenes, etc.)
data/        # Artefactos locales (no versionar)
```

## Requisitos
- Windows x64, Python 3.10+ (recomendado 3.11/3.12).
- `pip install -r requirements.txt`

## Variables clave
- `TSC_GETDATA_FILE` → ruta a `GetData.txt` de RailWorks.
- `LUA_BUS_PATH` → ruta de salida del bus (por defecto `data/lua_eventbus.jsonl`).
- `TSC_FAKE_RD=1` → backend simulado para pruebas sin hardware.

## Calidad
```powershell
pytest -q
ruff check .
# opcional
mypy runtime tools --strict
```

## Documentación
- [Frenada v0 (especificación y uso)](docs/frenada_v0.md)
- [Higiene del repositorio / datos y .gitignore](docs/repo_limpieza.md)
- [Índice de documentación](docs/README.md)

## Contribuciones (patches mínimos)
> Propón cambios **pequeños** y enfocados, con tests. Evita reescrituras masivas.
Incluye diffs por archivo (`*** Begin Patch …`) y separa archivos nuevos.

