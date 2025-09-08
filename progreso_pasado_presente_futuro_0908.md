# Progreso — Pasado / Presente / Futuro (0908)

## Estado actual (hechos)
- **Bridge GetData → bus** funcionando: aparecen `getdata_next_limit (kph, dist_m)` y `getdata_hello`.
- **Collector** sellando `t_wall` y `odom_m` y normalizando: `getdata_next_limit → meta.to / meta.dist_m`; `speed_limit_change` presentes.
- **Enriquecido** (`tools/dist_next_limit.py`) generando **`run.dist.csv`** con **`dist_next_limit_m`** continuo y decreciente hacia 0 cerca de la señal.
- **Artefactos recientes**: `run.csv`, `run.dist.csv`, `lua_eventbus.jsonl`, `events.jsonl` coherentes.

## Hecho hoy (pasado reciente)
1) **Fix DLL 64‑bit**: `ingestion/rd_client.py` elige `RailDriver64.dll` en Python 64‑bit (+ overrides por env).
2) **Collector**: estampa siempre `e["odom_m"]` y `e["t_wall"]` **antes** de normalizar.
3) **Normalizador**: mapea `getdata_next_limit → meta.to/meta.dist_m`; mantiene `raw` y añade `limit_next_kmh/dist_est_m` como comodidad.
4) **Bridge GetData** (`ingestion/getdata_bridge.py`): tail de `plugins/GetData.txt`, emite `speed_limit_change` (actual) y `getdata_next_limit` (próximo+dist).
5) **Enriquecido**: preferencia por probes (`getdata_next_limit`) con fusión por `t_wall`; fallback a método por eventos.
6) **Housekeeping**: guía para archivar/borrar `train_sim_ai_readme_rapido_ci_patches_listos.md`.

## Ahora mismo (presente)
- **Verificación**: al cruzar una señal se observa `getdata_next_limit` con `dist_m` ≈ 10–30 m justo antes del `speed_limit_change` (sincronía correcta).
- **VSCode**:
  - `Pylance`: ya corregido el `fillna('ffill')` → usar `fillna(method='ffill')` (sin falsos positivos ahora).
  - `Ruff F401`: eliminar imports no usados (`typing.Dict`, `typing.Any`) o convertir a doc‑types si aplican.
  - **Interpreter**: seleccionar **.venv 64‑bit** (Ctrl‑Shift‑P → Python: Select Interpreter → `.venv` del repo).
  - **Testing**: `pytest -m "not integration"` por defecto; las pruebas de integración se ejecutan solo localmente.

## Próximo (futuro inmediato)
1) **Anti‑spam** en bridge: emitir `getdata_next_limit` solo si cambia `kph` o `dist_m` ±25 m (reducción de ruido).
2) **Plot combinado**: velocidad + `dist_next_limit_m` + marcas de `speed_limit_change` (validación visual de frenada).
3) **CI** (GitHub Actions): job de `pytest -m "not integration"` + ruff + mypy opcional.
4) **Opcional**: añadir `ScenarioScript.lua` plantilla para rutas sin GetData.

## Backlog (futuro cercano)
- **Curvas de frenado** (ERA): objetivo de velocidad en función de `dist_next_limit_m` y margen configurable.
- **Autopiloto básico**: PID sobre acelerador/freno con objetivo dinámico según curva de frenado.
- **Wrapper en loco** (cuando cerremos Serz/XML): `<EngineScript>` → wrapper LUA genérico o `getdata`.
- **Documentación**: diagrama de flujo de ingestión y enriquecido; guía de troubleshooting.

---

## VSCode — configuración recomendada

### Archivos nuevos
**`.vscode/extensions.json`**
```json
{
  "recommendations": [
    "ms-python.python",
    "ms-python.vscode-pylance",
    "charliermarsh.ruff",
    "ms-toolsai.jupyter",
    "ms-vscode.powershell"
  ]
}
```

**`.vscode/settings.json`**
```json
{
  "python.defaultInterpreterPath": ".venv/Scripts/python.exe",
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["-m", "not integration"],
  "ruff.lint.args": ["--line-length", "100"],
  "editor.formatOnSave": true,
  "files.eol": "\n",
  "files.insertFinalNewline": true
}
```

**`.vscode/tasks.json`**
```json
{
  "$schema": "https://schema.store/schemas/json/tasks.json",
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Bridge: GetData",
      "type": "shell",
      "command": ".venv/Scripts/python.exe -m ingestion.getdata_bridge",
      "options": { "env": { "TSC_GETDATA_FILE": "C:/Program Files (x86)/Steam/steamapps/common/RailWorks/plugins/GetData.txt" } },
      "problemMatcher": []
    },
    {
      "label": "Collector",
      "type": "shell",
      "command": ".venv/Scripts/python.exe -m runtime.collector --hz 10 --bus-from-start",
      "problemMatcher": []
    },
    {
      "label": "Enriquecer run",
      "type": "shell",
      "command": ".venv/Scripts/python.exe tools/dist_next_limit.py",
      "problemMatcher": []
    },
    {
      "label": "Tests (unit)",
      "type": "shell",
      "command": ".venv/Scripts/python.exe -m pytest -q -m \"not integration\"",
      "problemMatcher": []
    }
  ]
}
```

**`.vscode/launch.json`**
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Bridge GetData (module)",
      "type": "python",
      "request": "launch",
      "module": "ingestion.getdata_bridge",
      "justMyCode": true
    },
    {
      "name": "Python: Collector (module)",
      "type": "python",
      "request": "launch",
      "module": "runtime.collector",
      "args": ["--hz", "10", "--bus-from-start"],
      "justMyCode": true
    },
    {
      "name": "Python: Pytest (unit only)",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": ["-q", "-m", "not integration"],
      "justMyCode": true
    }
  ]
}
```

**`pytest.ini`** *(nuevo)*
```ini
[pytest]
addopts = -q
markers =
    integration: pruebas que requieren datos reales en data/ (se omiten en CI)
```

> Si ya tienes `pyproject.toml` con Ruff, puedes añadir `line-length = 100`. Evita desactivar `F401`: mejor limpiar imports no usados.

---

## Problemas comunes en VSCode y cómo resolverlos
- **`Pylance: reportCallIssue (fillna)`** → usar `fillna(method="ffill")` (firmas tipadas correctas).
- **`Ruff F401` (unused import)** → eliminar/usar los imports; o convertir a hints en docstring si solo documentan.
- **Intérprete incorrecto** → seleccionar `.venv` (64‑bit). Si sale `WinError 193`, estás en 32‑bit o DLL errónea.
- **XML→BIN a 0 bytes** → nunca editar desde XML vacío; extraer desde BIN original con `Serz.exe`, editar **UTF‑8**, compilar en carpeta temporal y copiar.
- **Ruta de `GetData.txt`** → define `TSC_GETDATA_FILE` o ajusta `tasks.json`.

---

## To‑do inmediato (checklist)
- [ ] Confirmar que `events.jsonl` ya trae `getdata_next_limit` con `t_wall` y `meta.dist_m`.
- [ ] Ejecutar tests unitarios (`pytest -m "not integration"`) y dejar 💚 en VSCode.
- [ ] Añadir anti‑spam (±25 m) al bridge si el log es muy verboso.
- [ ] Generar `run.dist.csv` tras una pasada completa por una señal (ver cruce por ~0 m).
- [ ] (Opcional) Añadir workflow de CI en `.github/workflows/ci.yml` con ruff + pytest unit.

