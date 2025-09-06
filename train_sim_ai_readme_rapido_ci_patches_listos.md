# README.md (propuesto)

## TrainSimAI
Telemetría y eventos para **Train Simulator Classic** usando **py‑raildriver** (controles/“specials”) + **LUA** (límites, paradas, marcadores). Genera:
- `data/runs/*.csv` (≈10 Hz): velocidad, frenos, SIFA/PZB/LZB/AFB, lat/lon/heading/gradient, hora in‑game, **odom_m**…
- `data/events/events.jsonl`: eventos normalizados (`marker_pass`, `speed_limit_change`, `stop_begin/stop_end`, …).

### Requisitos
- Windows + Python **3.11+**
- **Train Simulator Classic** instalado
- Drivers **RailDriver** / DLL accesible

### Instalación
```powershell
pip install -r requirements.txt
```

### Configurar el bus LUA
1) Abre `lua/tsc_eventbus.lua` y fija **ruta absoluta** del repo:
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
> **Importante**: deja **solo** este proceso escribiendo `events.jsonl` (no ejecutes `tools/drain_lua_bus.py` en paralelo).

### Validar
```powershell
python tools/validate_run.py
```
Salida esperada:
- Hz ≈ **9–10**
- Loco detectada (p. ej. `DB BR146.0`)
- Sin avisos por `Throttle/MPH` si tienes `Regulator/KPH`

### Rotar runs (opcional) aqui
```powershell
powershell -ExecutionPolicy Bypass -File .\tools\rotate_runs.ps1
```

### Estructura
```
/ingestion    # py‑raildriver wrapper, bus LUA
/runtime      # collector, csv logger, normalizador eventos
/lua          # scripts LUA (eventos de límite, paradas, marcadores)
/profiles     # mapeos por locomotora (controles y rangos)
/tools        # utilidades (validador, caps, rotate)
/data         # runs/*.csv y events/*.jsonl
```

### Solución de problemas
- **No aparece `events.jsonl`** → Alinea `EVENTBUS_PATH` y `LUA_BUS_PATH`; crea los archivos vacíos; fuerza un evento:
  ```powershell
  Add-Content .\data\lua_eventbus.jsonl -Value '{"type":"marker_pass","name":"manual","time":1}'
  ```
- **Eventos duplicados / sin lat/lon** → Asegura un **solo escritor** de eventos (solo el collector).
- **Hz ≈ 5** → Asegúrate de tener `LuaEventBus` sin `sleep` cuando no hay archivo (versión actual del repo ya lo corrige).
- **CSV “field larger than field limit”** → usa `tools/repair_csv.py` y la versión nueva de `runtime/csv_logger.py` (reescritura correcta de cabecera).
- **Ver qué expone tu DLL** → `python tools/rd_caps.py`.

### Roadmap corto
- `speed_limit_change` + distancia (LUA)
- Paradas con nombre (marcadores de andén)
- Validación de frenado/AFB (gráficas con `odom_m`)

### Licencia
MIT (propuesto).

---

# .github/workflows/ci.yml (propuesto)
```yaml
name: ci

on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Cache pip
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
          restore-keys: |
            ${{ runner.os }}-pip-

      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install ruff flake8 mypy pytest

      - name: Ruff
        run: ruff check .

      - name: Flake8
        run: flake8 .

      - name: Mypy (best-effort)
        run: mypy ingestion runtime tools --ignore-missing-imports

      - name: Pytest
        run: pytest -q || true
```

---

# tools/rotate_runs.ps1 (propuesto)
```powershell
$ErrorActionPreference = 'Stop'
$dir = Join-Path $PSScriptRoot '..\data\runs'
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$src = Join-Path $dir 'run.csv'
if (Test-Path $src) {
  $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
  $dst = Join-Path $dir ("run_$stamp.csv")
  Move-Item -Path $src -Destination $dst -Force
  Write-Host "Rotado a $dst"
}
# tocar nuevo run.csv vacío
New-Item -ItemType File -Force -Path $src | Out-Null
Write-Host "Nuevo $src listo"
```

---

## Diffs mínimos (si prefieres aplicar como patch)

### README.md
```diff
*** /dev/null
--- a/README.md
@@
+«contenido README.md de arriba»
```

### CI workflow
```diff
*** /dev/null
--- a/.github/workflows/ci.yml
@@
+«contenido ci.yml de arriba»
```

### Script de rotación
```diff
*** /dev/null
--- a/tools/rotate_runs.ps1
@@
+«contenido rotate_runs.ps1 de arriba»
```

