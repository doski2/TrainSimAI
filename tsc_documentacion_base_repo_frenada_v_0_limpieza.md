# TrainSimAI (TSC) — Documentación base

> **Objetivo**: Dejar el proyecto listo para trabajar (Windows, Python 64‑bit) con guía de ejecución, limpieza del repo, y especificación de **Frenada v0** (offline/online) para revisión.

---

## 1) Resumen ejecutivo
- **Bridge GetData → Bus LUA** ✅ (`ingestion.getdata_bridge`) — Emite `getdata_next_limit` con `kph` y `dist_m`.
- **Collector** ✅ (`runtime.collector`) — Sella `t_wall` y `odom_m`, normaliza `meta.to`/`meta.dist_m`, y vuelca `events.jsonl`.
- **tools/dist_next_limit.py** ✅ — Genera `data/run.dist.csv` con `dist_next_limit_m` (serie continua/decreciente por `t_wall`).
- **Frenada v0** (nuevo) — Cálculo de **velocidad objetivo** en kph con margen configurable y A (deceleración servicio). Versión **offline** lista; integración **online** propuesta.
- **Tests** — Unitarios (normalización + probes + frenada/pid) listos para ampliar.

---

## 2) Estructura del repo (roles)
```
/ingestion        # Bridges y captura (GetData → bus LUA)
/runtime          # Collector, control en vivo, módulos de lógica (frenada/pid)
/tools            # Utilidades offline: distancias, merges, plots, drains
/tests            # Unitarios/integ.
/lua              # Scripts LUA auxiliares (si aplica)
/profiles         # Perfiles por locomotora/escenario (A, márgenes, etc.)
/docs             # Dossier, roadmap, diseño (mover aquí PDFs/MD de la raíz)
/vendor           # (opcional) terceros vendorizados con licencia
/data             # Artefactos locales: CSV, JSONL, runs, events (no versionar)
```

---

## 3) Flujos de ejecución
### 3.1 Bridge (GetData → Bus)
```powershell
$env:TSC_GETDATA_FILE="C:\\Program Files (x86)\\Steam\\steamapps\\common\\RailWorks\\plugins\\GetData.txt"
python -m ingestion.getdata_bridge
```
Salida: `data/lua_eventbus.jsonl` (o ruta configurada por env var `LUA_BUS_PATH`).

### 3.2 Collector (normaliza y enriquece)
```powershell
python -m runtime.collector --hz 10 --bus-from-start
```
Salidas:
- `data/events.jsonl` (eventos normalizados: `getdata_next_limit`, `speed_limit_change`, etc.)
- `data/run.csv` (telemetría base con `t_wall`, `odom_m`, `speed_kph`, ...)

### 3.3 Distancia al próximo límite
```powershell
python -m tools.dist_next_limit
```
Salida: `data/run.dist.csv` con `t_wall` + `dist_next_limit_m`.

### 3.4 Frenada v0 (offline)
```powershell
python -m tools.apply_frenada_v0 \
  --log data/run.csv \
  --dist data/run.dist.csv \
  --events data/events.jsonl \
  --out data/run.ctrl.csv \
  --A 0.7 --margin-kph 3 --reaction 0.6
```
Salida: `data/run.ctrl.csv` (añade `target_speed_kph`, `phase`).

### 3.5 Plot de validación
```powershell
python -m tools.plot_run data/run.ctrl.csv
```
- Traza `speed_kph`, `target_speed_kph` (si existe) y segundo eje `dist_next_limit_m`.

---

## 4) Variables de entorno / rutas clave
- `TSC_GETDATA_FILE` → `C:\\Program Files (x86)\\Steam\\steamapps\\common\\RailWorks\\plugins\\GetData.txt`
- `LUA_BUS_PATH` → por defecto `data/lua_eventbus.jsonl`
- `TSC_FAKE_RD=1` → habilita backend simulado (tests/ensayos sin hardware).

---

## 5) Pipeline de datos (archivos)
- **Entrada**: `GetData.txt` (lectura periódica por bridge).  
- **Bus**: `data/lua_eventbus.jsonl` (append‑only).  
- **Collector**: `data/events.jsonl` y `data/run.csv`.  
- **Distancias**: `data/run.dist.csv` (por `tools/dist_next_limit.py`).  
- **Frenada offline**: `data/run.ctrl.csv` (merge + objetivos).  

> Recomendación: no versionar `/data/*` (ver `.gitignore` propuesto).

---

## 6) Frenada v0 — Especificación
**Objetivo**: calcular una **velocidad objetivo** segura (kph) para llegar al próximo límite `next_limit_kph` respetando un margen.

**Fórmula** (espacio):
```
v_safe^2 = v_lim^2 + 2 * A * d_eff
v_lim = max(0, next_limit_kph - margin_kph)
d_eff = max(0, dist_next_limit_m - v_now_mps * reaction_time_s)
```
- `A` → deceleración de servicio (>0) en m/s² (por loco; valor inicial 0.7).  
- `reaction_time_s` → latencia combinada (sensado/actuador).  
- `gradient_pct` (opcional) → ajusta A con clamp (0.6–1.4) para pendiente.  
- **Salida**: `target_speed_kph = min(v_now_kph, v_safe_kph)` con cota inferior `min_target_kph`.

**Fases**:
- `BRAKE` si `target < now - coast_band`.  
- `COAST` si `|target - now| <= coast_band`.  
- `CRUISE` si `target > now + coast_band`.

**Parámetros por defecto** (`runtime/braking_v0.BrakingConfig`):
- `margin_kph=3.0`, `max_service_decel=0.7`, `reaction_time_s=0.6`, `min_target_kph=5.0`, `coast_band_kph=1.0`.

---

## 7) Integración online (bucle de control)
```python
from runtime.braking_v0 import compute_target_speed_kph, BrakingConfig
from runtime.pid import SplitPID

cfg = BrakingConfig()
pid = SplitPID()

# en cada tick (dt):
v_obj, fase = compute_target_speed_kph(v_now_kph, next_limit_kph, dist_next_limit_m, cfg=cfg)
th, br = pid.update(v_obj, v_now_kph, dt)
# aplicar th/br vía backend real o simulado (TSC_FAKE_RD)
```
**Guardas** recomendadas: `overspeed_guard` (si `speed_kph > next_limit_kph + δ`, fuerza freno), limitación de cambios bruscos y rate‑limit en comandos de actuador.

---

## 8) QA & Tests
- **Unitarios**: `tests/test_braking_v0.py`, `tests/test_pid.py` (signos, margen, monotonicidad/objetivo).  
- **Smoke**:
```powershell
pytest tests/test_braking_v0.py -q
pytest tests/test_pid.py -q
```
- **Rendimiento**: valida que `dist_next_limit_m` sea **decreciente** y que `target_speed_kph` **descienda** al acercarte al límite.

---

## 9) Mantenimiento y limpieza del repo
### 9.1 Eliminar (seguros)
- `stdout.txt`, `stderr.txt`, `stderr2.txt`, `tmp_head.txt`, `tmp_tail.txt` (artefactos locales).

### 9.2 Mover a `/docs`
- Dossier/roadmap/planes (`AGENTS.md`, `train_sim_ai_plan_de_iteracion_v_1_0906.md`, `tsc_2024_*.md`, PDFs).

### 9.3 `py-raildriver-master/`
- Si **sin parches propios**, reemplazar por dependencia `pip` y eliminar carpeta.  
- Si **con parches**, mover a `vendor/py-raildriver/` con LICENSE y origen.

### 9.4 `.gitignore` recomendado (fragmento)
```gitignore
__pycache__/
.pytest_cache/
.venv/
.env*
*.egg-info/
*.coverage
coverage.xml
.vscode/
/data/*.csv
/data/*.parquet
/data/*.json
/data/*.jsonl
/data/runs/
/data/events/
/data/lua_eventbus.jsonl
*.log
*.tmp
*.bak
stdout.txt
stderr*.txt
tmp_*.txt
.DS_Store
Thumbs.db
```

---

## 10) VS Code — tareas útiles (opcional)
`/.vscode/tasks.json` (crea si no existe):
```json
{
  "version": "2.0.0",
  "tasks": [
    {"label": "Bridge GetData", "type": "shell", "command": "python -m ingestion.getdata_bridge"},
    {"label": "Collector (10 Hz)", "type": "shell", "command": "python -m runtime.collector --hz 10 --bus-from-start"},
    {"label": "Dist next limit", "type": "shell", "command": "python -m tools.dist_next_limit"},
    {"label": "Frenada offline", "type": "shell", "command": "python -m tools.apply_frenada_v0 --log data/run.csv --dist data/run.dist.csv --events data/events.jsonl --out data/run.ctrl.csv --A 0.7 --margin-kph 3 --reaction 0.6"},
    {"label": "Plot run", "type": "shell", "command": "python -m tools.plot_run data/run.ctrl.csv"},
    {"label": "Pytest (rápido)", "type": "shell", "command": "pytest -q"}
  ]
}
```
> Puedes lanzar desde `Terminal → Run Task…`.

---

## 11) Notas para Copilot/Codex (buenas prácticas)
- **Pedir diffs mínimos** y respetar nombres/rutas.  
- **Separar archivos nuevos** (no mezclar en un patch masivo).  
- **Evitar reescribir** `collector` completo: pedir *hooks* o funciones nuevas y llamadas puntuales.  
- **Proveer tests** por cada cambio.

**Prompt base útil** (copiar/pegar):
> “Propón cambios mínimos para añadir X. Devuélveme solo un `*** Begin Patch` por archivo tocado y archivos nuevos separados. Incluye tests y comandos de prueba. Mantén estilos/typing actuales. No cambies nada más.”

---

## 12) Próximos pasos
1. Parametrizar `A` (deceleración) por **locomotora** (`/profiles/*.json`).  
2. Añadir `overspeed_guard` y *rate limiter* a salidas de `SplitPID`.  
3. Registrar `v_obj`, `fase`, `th`, `br` en `csv_logger` (para análisis).  
4. CI: job con `pytest` + `ruff` + `mypy`.

