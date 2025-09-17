# Perfiles TSC (tren)

## Campos soportados por el controlador
- `a_service_mps2` (float): deceleración de servicio [m/s²]. BR146 ≈ 1.0.
- `t_react_s` (float): tiempo de reacción total [s] (retardo + latencia).
- `margin_m` (float): colchón de distancia adicional.
- `v_margin_kph` (float): margen de velocidad respecto al límite [km/h].
- `era_curve_csv` (opcional): csv de curva de esfuerzo/par si aplica.

> El controlador usa estos campos **en la raíz** del JSON.

## Recomendación BR146 (estable)
```json
{
  "name": "DB BR146",
  "era_curve_csv": "profiles/BR146_era_curve.csv",
  "a_service_mps2": 1.0,
  "t_react_s": 1.3,
  "margin_m": 140.0,
  "v_margin_kph": 6.5
}
```
