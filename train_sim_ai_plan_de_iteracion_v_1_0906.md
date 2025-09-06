# TrainSimAI — Plan de iteración y documentación v1

> Documento maestro de trabajo para las próximas 1–2 iteraciones. Mantenerlo actualizado con cada entrega (diffs mínimos y archivos nuevos separados).

---

## 1) Resumen
Vamos a priorizar **observabilidad y validación** sin tocar la lógica de control. Primero veremos y mediremos con lo que ya emitimos (CSV + eventos). Después añadiremos el cálculo **offline** de `dist_next_limit_m` y, cuando esté validado, pasaremos a la fuente LUA.

**Objetivos de esta iteración:**
- Visualización rápida de **velocidad vs. límite** con marcas de eventos y `odom_m`.
- Conveniencia de entorno y **smoke test** reproducible en Windows.
- Definir un **schema v1** de eventos (campos y ejemplo) para tests ligeros.
- Preparar el cálculo offline de **distancia al próximo cambio de límite**.
- (Siguiente parche) Fix pequeño de typing/robustez en `runtime/csv_logger.py`.

---

## 2) Estado actual (resumen)
- Se generan `data/runs/*.csv` (≈9–12 Hz) y `data/events/events.jsonl` con eventos normalizados (`speed_limit_change`, `marker_pass`, `limit_reached`, `stop_begin/stop_end`, …).
- Modo simulado activable: `TSC_FAKE_RD=1`.
- `runtime.collector` con flags útiles: `--duration`, `--hz`, `--bus-from-start`.
- Pipeline de plotting y validación: lo unificamos con un script nuevo (abajo).

---

## 3) Entregables **nuevos** (copiar y pegar)
Los siguientes archivos son **nuevos**. Pégalos tal cual en el repo.

### 3.1) `scripts/quickstart.ps1`
Conveniencia de entorno y **smoke test** rápido para Windows.

```powershell
# scripts/quickstart.ps1
# Uso: PowerShell -ExecutionPolicy Bypass -File .\scripts\quickstart.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Raíz del repo = carpeta actual del script
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

# 1) Crear carpetas y archivos base
New-Item -ItemType Directory -Force -Path .\data, .\data\events, .\data\runs | Out-Null
New-Item -ItemType File -Force -Path .\data\lua_eventbus.jsonl, .\data\events\events.jsonl | Out-Null

# 2) Exportar LUA_BUS_PATH para collector
$env:LUA_BUS_PATH = (Join-Path $RepoRoot 'data\lua_eventbus.jsonl')

Write-Host "LUA_BUS_PATH = $env:LUA_BUS_PATH"

# 3) Smoke test (modo simulado opcional)
if (-not $env:TSC_FAKE_RD) {
  Write-Host "Tip: si no tienes hardware/DLL, activa modo simulado:"
  Write-Host '$env:TSC_FAKE_RD = "1"'
}

# 4) Ejecución corta del collector (5s a 12Hz)
python -m runtime.collector --duration 5 --hz 12

Write-Host "OK. Archivos esperados:"
Write-Host "  - data\runs\*.csv (muestras ~9-12Hz)"
Write-Host "  - data\events\events.jsonl (eventos normalizados)"
Write-Host ""
Write-Host "Siguiente: python tools\plot_last_run.py"
```

### 3.2) `tools/plot_last_run.py`
Abre el **último CSV** en `data/runs`, lee `events.jsonl` y dibuja velocidad, límite si existe, líneas de evento y `odom_m`.

```python
# tools/plot_last_run.py
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import pandas as pd


RUNS_DIR = Path("data/runs")
EVENTS_PATH = Path("data/events/events.jsonl")


@dataclass
class Event:
    type: str
    t_wall: float | None
    t_game: float | None
    odom_m: float | None
    raw: dict


def _latest_csv(runs_dir: Path) -> Path:
    csvs = sorted(runs_dir.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not csvs:
        raise SystemExit(f"No se encontraron CSV en {runs_dir}")
    return csvs[0]


def _read_events(path: Path) -> list[Event]:
    out: list[Event] = []
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            out.append(
                Event(
                    type=str(obj.get("type")),
                    t_wall=float(obj.get("t_wall")) if obj.get("t_wall") is not None else None,
                    t_game=float(obj.get("t_game")) if obj.get("t_game") is not None else None,
                    odom_m=float(obj.get("odom_m")) if obj.get("odom_m") is not None else None,
                    raw=obj,
                )
            )
    return out


def _maybe(series: pd.Series, *candidates: str) -> pd.Series | None:
    for name in candidates:
        if name in series:
            return series[name]
    return None


def main() -> None:
    csv_path = _latest_csv(RUNS_DIR)
    print(f"Usando CSV: {csv_path}")

    df = pd.read_csv(csv_path)

    # Columnas habituales (robusto a nombres)
    t = _maybe(df, "t_wall", "time_wall_s", "time", "t") or pd.Series(range(len(df)))
    v = _maybe(df, "speed_kph", "kph", "speed_kmh")
    limit = _maybe(df, "limit_kph", "speed_limit_kph", "limit")
    odom = _maybe(df, "odom_m", "distance_m", "odom")

    if v is None:
        raise SystemExit("No encuentro columna de velocidad (p.ej. 'speed_kph').")

    # Gráfico 1: velocidad (y límite si existe)
    plt.figure()
    plt.plot(t, v, label="velocidad (kph)")
    if limit is not None:
        plt.plot(t, limit, label="límite (kph)")

    # Eventos
    events: list[Event] = _read_events(EVENTS_PATH)
    for ev in events:
        x = ev.t_wall if ev.t_wall is not None else ev.t_game
        if x is None:
            continue
        plt.axvline(x=x, linestyle="--")
    plt.legend()
    plt.xlabel("tiempo")
    plt.ylabel("kph")
    plt.title(csv_path.name)

    # Gráfico 2: odómetro si existe
    if odom is not None:
        plt.figure()
        plt.plot(t, odom)
        plt.xlabel("tiempo")
        plt.ylabel("odom_m")
        plt.title("odom_m")

    plt.show()


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        print(e, file=sys.stderr)
        sys.exit(2)
```

---

## 4) Cómo ejecutar (copiar/pegar)

```powershell
# Desde la raíz del repo
powershell -ExecutionPolicy Bypass -File .\scripts\quickstart.ps1

# Visualizar el último run
python .\tools\plot_last_run.py
```

Resultado esperado:
- `data/runs/xxxxx.csv` nuevo con ~5 s de datos.
- `data/events/events.jsonl` con líneas de eventos.
- Dos ventanas de matplotlib: (1) velocidad vs. límite + líneas de eventos; (2) `odom_m` (si existe).

---

## 5) Schema de eventos v1 (para tests y tooling)
**Campos mínimos por evento:**
- `type` (str) — p.ej. `"speed_limit_change"`, `"marker_pass"`, `"stop_begin"`, `"stop_end"`, `"limit_reached"`.
- `t_game` (float, opcional) — timestamp de juego.
- `t_wall` (float, opcional) — timestamp real.
- `odom_m` (float, opcional) — odómetro en metros (si está disponible).
- `meta` (dict) — payload del evento (p.ej., `{"from":120, "to":100}` en cambios de límite).
- `id` (str, opcional) — identificador único para correlación.

**Ejemplo (una línea JSONL):**
```json
{"type":"speed_limit_change","t_wall":123.45,"t_game":321.0,"odom_m":1540.8,"meta":{"from":120,"to":100},"id":"ev-00023"}
```

**Motivación:** este núcleo permite hacer tests de forma y derivar señales offline (como `dist_next_limit_m`).

---

## 6) Validación (proceso corto)
1. Ejecutar **smoke test** con `quickstart.ps1`.
2. Lanzar `tools/plot_last_run.py` y confirmar:
   - La serie de **velocidad** evoluciona suave y con muestras regulares.
   - Si hay columna de **límite**, se dibuja; si no, no es bloqueante.
   - Las **líneas de evento** aparecen donde esperamos (cambios de límite, marcas, inicios/fin de parada, …).
   - `odom_m` (si existe) crece monótonamente.
3. Guardar captura de la figura (opcional) para históricos.

**KPIs mínimos:**
- % de muestras con `odom_m` no nulo.
- % de eventos con `t_wall` o `t_game` no nulos.
- (Cuando tengamos `limit_kph`) % de tiempo dentro del límite ±1 kph.

---

## 7) Cálculo offline: `dist_next_limit_m` (diseño)
**Objetivo:** para cada fila del CSV, la distancia hasta el próximo evento `speed_limit_change` medido en `odom_m`.

**Inputs:**
- `data/runs/<ultimo>.csv` (columnas: `t_wall`/`t`, `odom_m`, `speed_kph`, opcional `limit_kph`).
- `data/events/events.jsonl` (eventos con `type == "speed_limit_change"` y `odom_m`).

**Salida:**
- CSV enriquecido con columna `dist_next_limit_m`.

**Pasos:**
1. Cargar eventos y filtrar `speed_limit_change` con `odom_m` válido; ordenar por `odom_m` asc.
2. Cargar el CSV y asegurar `odom_m` monótono (si hay regresión brusca, marcar como gap).
3. Para cada muestra, buscar el **siguiente** `odom_m` de cambio de límite y restar.
4. Persistir como `data/runs/<ultimo>.dist.csv` o escribir a `stdout` para piping.

**Interfaz prevista (próximo parche):**
```bash
python tools/dist_next_limit.py --run data/runs/<ultimo>.csv --events data/events/events.jsonl --out data/runs/<ultimo>.dist.csv
```

**Uso inmediato:** este valor habilita validación de **curvas de frenado** y métricas de anticipación.

---

## 8) `runtime/csv_logger.py` — fix de typing (plan)
**Problema:** aviso Pylance `"writeheader" is not a known attribute of "None"` debido a writer tipado como opcional.

**Solución propuesta (parche mínimo, próxima entrega):**
- Declarar `self._writer: csv.DictWriter[str] | None = None`.
- Asignar al abrir el archivo.
- Añadir `assert self._writer is not None` justo antes de `self._writer.writeheader()` o proteger con `if self._writer:`.

**Criterio de aceptación:** sin avisos de Pylance/Mypy, comportamiento idéntico.

---

## 9) Normas de entrega en este proyecto
- **Parches mínimos** en diff unificado, un archivo por bloque de cambio.
- **Archivos nuevos** siempre separados en su propia sección.
- Comandos **listos para pegar** (PowerShell y/o Python).
- Cada propuesta va acompañada de **prueba interna** (script de test/plot o verificación rápida).

---

## 10) Roadmap inmediato (próximo parche)
- **A)** Diff para `runtime/csv_logger.py` (typing/robustez) + test corto de escritura.
- **B)** Nuevo `tools/dist_next_limit.py` con CLI, docstring y prueba sobre el último run.

**Hecho =**
- Pasa Mypy/Ruff (si están configurados).
- Genera `*.dist.csv` con columna `dist_next_limit_m`.
- Gráfico adicional opcional: `dist_next_limit_m` vs tiempo.

---

## 11) Troubleshooting rápido
- *No aparece ningún CSV:* verifica permisos y que `python -m runtime.collector` no muestre excepciones.
- *No hay ventana de gráficos:* comprueba que `matplotlib` esté instalado; si usas venv, actívalo antes.
- *No se dibuja el límite:* aún no hay columna `limit_kph`; no bloquea el resto del flujo.
- *Eventos vacíos:* confirma ruta `data/events/events.jsonl` y que el collector escriba en esa ubicación.

---

## 12) Apéndice: convenciones de columnas
- Velocidad: preferente `speed_kph` (alias `kph`, `speed_kmh`).
- Límite: preferente `limit_kph` (alias `speed_limit_kph`, `limit`).
- Tiempo: preferente `t_wall` (alias `time_wall_s`, `time`, `t`).
- Odómetro: preferente `odom_m` (alias `distance_m`, `odom`).

---

**Fin de documento v1.** Mantenerlo como fuente única de verdad durante la iteración actual.

