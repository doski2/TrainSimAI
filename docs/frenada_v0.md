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
 `margin_m`: margen de distancia antes del hito (p.ej. 70 m)
 `v_margin_kph`: margen bajo el límite (p.ej. 2.0 kph)

## Suavidad (Jerk)
Se aplica un **JerkBrakeLimiter** que limita la tasa de cambio del freno y la variación de esa tasa. Mejora confort y evita “serrucho”.

## Criterios de aceptación (v0)
`dist_next_limit_m` decrece monótona (sin subidas > 2 m dentro del mismo límite).
**Llegada**: en `dist <= 5 m`, velocidad ≤ `límite + 0.5 kph` al menos en el **90%** de los casos.
**Últimos 50 m**: margen medio `límite - velocidad` ≈ **+0.5…+1.0 kph**.
**Overspeed guard** entra siempre que `speed > limit + 0.5 kph`.

## Tuning rápido
1. Si llegas “largo”: sube `margin_m` (+10…+20 m).  
2. Si quieres llegar un poco más “retenido”: sube `v_margin_kph` (+0.5).  
3. Si frena “a saltos”: baja `max_jerk_per_s2` (p.ej. 2.0) en `JerkBrakeLimiter`.
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

