# Frenada v0 — Especificación

**Objetivo**: calcular una **velocidad objetivo** segura (kph) para alcanzar el próximo límite `next_limit_kph` respetando un margen.

## Fórmulas
```
v_safe^2 = v_lim^2 + 2 * A * d_eff
v_lim = max(0, next_limit_kph - margin_kph)
d_eff = max(0, dist_next_limit_m - v_now_mps * reaction_time_s)
```
Donde:
- `A` (m/s²) es la deceleración de servicio (>0, por locomotora).
- `reaction_time_s` compensa latencias de sensado/actuación.
- Ajuste opcional por `gradient_pct` (pendiente): factor sobre `A` con clamp [0.6, 1.4].

**Salida**: `target_speed_kph = min(v_now_kph, v_safe_kph)` con cota inferior de seguridad.

## Fases
- `BRAKE`: `target < now - coast_band`
- `COAST`: `|target - now| <= coast_band`
- `CRUISE`: `target > now + coast_band`

## Parámetros por defecto (sugeridos)
- `margin_kph = 3.0`
- `max_service_decel = 0.7`
- `reaction_time_s = 0.6`
- `coast_band_kph = 1.0`
- `min_target_kph = 5.0`

## Flujo offline
```powershell
python -m tools.apply_frenada_v0 `
  --log data/run.csv `
  --dist data/run.dist.csv `
  --events data/events.jsonl `
  --out data/run.ctrl.csv `
  --A 0.7 --margin-kph 3 --reaction 0.6
python -m tools.plot_run data/run.ctrl.csv
```

## Integración online (bucle)
```python
from runtime.braking_v0 import compute_target_speed_kph, BrakingConfig
from runtime.pid import SplitPID

cfg = BrakingConfig()
pid = SplitPID()
v_obj, fase = compute_target_speed_kph(v_now_kph, next_limit_kph, dist_next_limit_m, cfg=cfg)
th, br = pid.update(v_obj, v_now_kph, dt)
```
Recomendado: `overspeed_guard`, limitación de rate en actuadores y log de `v_obj/fase/th/br`.

