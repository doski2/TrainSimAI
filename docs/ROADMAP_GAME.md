# Train Simulator Classic 2024 — Roadmap de Juego

Este documento define una hoja de ruta orientada al juego para el proyecto "Train Simulator Classic 2024". Está pensado para el enfoque lúdico/simulador (no un sistema real de control ferroviario).

## Visión
Crear una experiencia de simulación de trenes con IA que pueda actuar como asistente o piloto automatizado dentro del juego, ofreciendo modos de juego (entrenamiento, desafío, competición) y métricas de entretenimiento (score, suavidad, realismo).

## Hitos principales

Hito 1 — Prototipo IA en simulador (estático)
- Objetivo: IA básica de control de freno y velocidad corriendo en el simulador con `runtime.control_loop` + `raildriver_stub`.
- Entregables:
  - Scripts de experimentos reproducibles (ej. `scripts/sweep_brake_params.py`) que generan métricas de juego.
  - Métricas básicas: score, suavidad (jerk/acc), penalizaciones (sobrefrenada, exceso de velocidad).
  - Tests unitarios que verifiquen comportamientos en escenarios simples.
- Criterio de aceptación: ejecución local reproducible y tests `not real` pasan.

Hito 2 — Mecánicas de juego y UI mínima
- Objetivo: integrar métricas con una UI/CLI que muestre score, record y feedback por maniobra.
- Entregables:
  - Runner de demo (modo entrenamiento) que carga un escenario y muestra métricas.
  - Sistema de checkpoints y guardrails (límites que penalizan o detienen el modo si hay fallo crítico).
- Criterio: demo jugable localmente, logging de métricas a CSV.

Hito 3 — Modos de desafío y competición
- Objetivo: diseñar escenarios de dificultad y tabla de puntuaciones.
- Entregables:
  - Modo contrarreloj, modo precisión (mantén suavidad), modo emergencias (fallos aleatorios).
  - Export/Import de runs para comparativa.
- Criterio: 3 escenarios jugables y puntuación reproducible.

Hito 4 — Integración de IA avanzada y balance de juego
- Objetivo: modelos o heurísticas que aprendan a maximizar score manteniendo realismo.
- Entregables:
  - Entrenamiento de agentes (opcional: aprendizaje por refuerzo en entornos simulados).
  - Curvas de dificultad y calibración de parámetros (usando sweep y tests automatizados).
- Criterio: mejoras medibles en score/estabilidad sobre baseline heurística.

## Métricas de juego (ejemplos)
- Score total: combinación lineal de suavidad (más puntos), adherencia a límites de velocidad (penalizaciones), tiempo objetivo.
- Suavidad: inversa del jerk RMS durante la sesión.
- Penalizaciones: ocurrencias de frenada brusca (delta > X), sobrefrenado (valor freno == 1.0 repetido), exceso de velocidad.
- Reproducibilidad: misma semilla de RNG y el mismo run file deben producir métricas iguales.

## Integración práctica con el repo actual
- `scripts/sweep_brake_params.py`: usarlo para generar runs y CSV de métricas de juego. Añadir columnas: `score`, `smoothness`, `penalties`.
- `runtime.control_loop`: exponer un modo `--game-mode` que active hooks de métricas (si no, usar wrapper externo que compute métricas a partir del `rd_send.log`).
- Tests: añadir tests parametrizados que validen que ciertas configuraciones producen score mayor que baseline.

## Runbook dev rápido (ejemplos)
- Ejecutar una demo local con stub (modo juego):

```powershell
# activar entorno virtual
& ./.venv/Scripts/Activate.ps1
# correr demo (usa raildriver stub y run file de ejemplo)
python -m runtime.control_loop --source csv --run data/runs/test_brake.csv --mode brake --rd runtime.raildriver_stub:rd --hz 5 --duration 12 --out out/demo.csv --game-mode
```

- Lanzar sweep de parámetros y generar CSV de métricas:

```powershell
python scripts/sweep_brake_params.py
# luego revisar data/sweep/summary.csv
```

- Ejecutar tests que no usan hardware real:

```powershell
pytest -q -m "not real"
```

## Prioridades de implementación (próximas tareas)
1. Añadir columnas de métricas de juego al `scripts/sweep_brake_params.py` y producir CSV compatible.
2. Añadir `--game-mode` a `runtime.control_loop` (si procede) o crear un wrapper que compute métricas desde `rd_send.log`.
3. Implementar UI/CLI simple para mostrar score y resumen post-run.
4. Crear tests unitarios de scoring y reproducibilidad.

## Notas finales
- Esto es un proyecto de juego/simulador: prioriza experiencia, reproducibilidad y feedback al jugador.
- Si quieres, implemento ahora la tarea 1 (modificar `scripts/sweep_brake_params.py` para añadir `score` y `smoothness`) y hago un commit local.

---
Documento generado automáticamente el 2025-09-26 para la rama `ci/precommit-and-real-tests`.
