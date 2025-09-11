# Frenada v0 — resumen

Este documento resume la estrategia de `frenada_v0` y apunta al documento completo `frenada_v0.md`.

Conceptos clave
- `A` (aceleración de frenada): factor que escala la deceleración objetivo.
- `margin-kph`: margen hacia la velocidad objetivo para calibrar anticipación.
- `reaction`: tiempo de reacción en segundos antes de la maniobra.

Ejemplo de uso (offline):

```bash
python -m tools.apply_frenada_v0 --log data/run.csv --dist data/run.dist.csv --events data/events.jsonl --out data/run.ctrl.csv --A 0.7 --margin-kph 3 --reaction 0.6
```

Consulta el documento completo con curvas y ejemplos en `docs/frenada_v0.md`.
