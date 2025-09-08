# Objetivo
Implementar **Frenada v0** usando `dist_next_limit_m` y un controlador básico (PID dividido tracción/freno). Entregas en **diffs** y **archivos nuevos separados**.

---

## Archivos NUEVOS

### 1) `runtime/braking_v0.py`
```diff
*** Begin Patch
*** Add File: runtime/braking_v0.py
+from __future__ import annotations
+
+"""Braking curve v0 for TrainSimAI.
+
+Calcula una velocidad objetivo decreciente para garantizar que, con una
+deceleración de servicio (constante) A, sea posible alcanzar el próximo
+**límite** (kph) justo en la baliza/posición indicada por `dist_next_limit_m`.
+
+Fórmula base: v_safe^2 = v_lim^2 + 2 * A * d
+  - v_safe: velocidad máxima admisible *ahora* (m/s)
+  - v_lim:  límite ajustado por margen (m/s)
+  - A:      magnitud de deceleración de servicio (>0) en m/s^2
+  - d:      distancia efectiva (m)
+
+`v_obj` = min(v_actual, v_safe) en kph.
+"""
+
+from dataclasses import dataclass
+from math import sqrt
+from typing import Optional, Tuple
+
+
+def clamp(v: float, lo: float, hi: float) -> float:
+    return hi if v > hi else lo if v < lo else v
+
+
+def kph_to_mps(v_kph: float) -> float:
+    return v_kph / 3.6
+
+
+def mps_to_kph(v_mps: float) -> float:
+    return v_mps * 3.6
+
+
+@dataclass(frozen=True)
+class BrakingConfig:
+    margin_kph: float = 3.0            # margen por debajo del límite
+    max_service_decel: float = 0.7     # m/s^2 (tuneable por loco)
+    reaction_time_s: float = 0.6       # latencia de reacción/actuador
+    min_target_kph: float = 5.0        # no pedir 0 salvo parada
+    coast_band_kph: float = 1.0        # banda muerta para COAST
+
+
+def effective_distance(dist_m: Optional[float], v_now_mps: float, cfg: BrakingConfig) -> float:
+    """Distancia efectiva descontando tiempo de reacción.
+
+    Si `dist_m` es None o negativa, tratamos como 0 (frenada inmediata deshabilitada).
+    """
+    if dist_m is None:
+        return 0.0
+    d = max(0.0, float(dist_m))
+    return max(0.0, d - v_now_mps * cfg.reaction_time_s)
+
+
+def compute_target_speed_kph(
+    v_now_kph: float,
+    next_limit_kph: Optional[float],
+    dist_next_limit_m: Optional[float],
+    *,
+    gradient_pct: Optional[float] = None,
+    cfg: BrakingConfig = BrakingConfig(),
+) -> Tuple[float, str]:
+    """Devuelve (v_objetivo_kph, fase_str).
+
+    Fases: "CRUISE" (acelera/mantén), "COAST" (sin tracción), "BRAKE" (freno).
+    Si no hay `next_limit_kph` o distancia, devuelve v_now y "CRUISE".
+    """
+    v_now_mps = kph_to_mps(max(0.0, v_now_kph))
+
+    if next_limit_kph is None:
+        return v_now_kph, "CRUISE"
+
+    v_lim_kph = max(0.0, next_limit_kph - cfg.margin_kph)
+    v_lim_mps = kph_to_mps(v_lim_kph)
+
+    # Ajuste muy simple por pendiente (opcional): reducir/elevar A un 10% por cada 2% de pendiente
+    A = cfg.max_service_decel
+    if gradient_pct is not None:
+        A *= clamp(1.0 + (-gradient_pct) * 0.05, 0.6, 1.4)
+
+    d_eff = effective_distance(dist_next_limit_m, v_now_mps, cfg)
+
+    # Si estamos ya por debajo del límite con margen y lejos, mantener/crucero.
+    if v_now_kph <= v_lim_kph - cfg.coast_band_kph and d_eff > 50.0:
+        return v_now_kph, "CRUISE"
+
+    # v_safe es la velocidad máxima que nos permite llegar al límite a tiempo.
+    v_safe_mps_sq = max(0.0, v_lim_mps * v_lim_mps + 2.0 * A * d_eff)
+    v_safe_mps = sqrt(v_safe_mps_sq)
+    v_safe_kph = mps_to_kph(v_safe_mps)
+
+    v_obj_kph = clamp(min(v_now_kph, v_safe_kph), max(cfg.min_target_kph, 0.0), 400.0)
+
+    # Heurística de fase
+    if v_obj_kph < v_now_kph - cfg.coast_band_kph:
+        phase = "BRAKE"
+    elif v_obj_kph <= v_now_kph + cfg.coast_band_kph:
+        phase = "COAST"
+    else:
+        phase = "CRUISE"
+
+    return v_obj_kph, phase
+
+
+__all__ = [
+    "BrakingConfig",
+    "compute_target_speed_kph",
+]
+
*** End Patch
```

### 2) `runtime/pid.py`
```diff
*** Begin Patch
*** Add File: runtime/pid.py
+from __future__ import annotations
+
+"""Split-PID para tracción/freno.
+
+Entrada: error_kph = v_obj - v_real
+Salida: (throttle:0..1, brake:0..1)
+
+Reglas:
+  - error > +deadband ⇒ tracción proporcional
+  - error < -deadband ⇒ freno proporcional
+  - banda muerta reduce caza.
+"""
+
+from dataclasses import dataclass
+
+
+def clamp01(x: float) -> float:
+    return 1.0 if x > 1.0 else 0.0 if x < 0.0 else x
+
+
+@dataclass
+class SplitPID:
+    kp_throttle: float = 0.06
+    kp_brake: float = 0.18
+    ki_throttle: float = 0.0
+    ki_brake: float = 0.0
+    kd_throttle: float = 0.0
+    kd_brake: float = 0.0
+    deadband_kph: float = 0.5
+    integral_limit: float = 5.0
+
+    _i_th: float = 0.0
+    _i_br: float = 0.0
+    _prev_err: float | None = None
+
+    def reset(self) -> None:
+        self._i_th = 0.0
+        self._i_br = 0.0
+        self._prev_err = None
+
+    def update(self, v_target_kph: float, v_now_kph: float, dt: float) -> tuple[float, float]:
+        err = v_target_kph - v_now_kph
+        d_err = 0.0 if self._prev_err is None else (err - self._prev_err) / max(dt, 1e-3)
+        self._prev_err = err
+
+        th, br = 0.0, 0.0
+
+        if err > self.deadband_kph:
+            self._i_th = clamp01(self._i_th + err * dt)
+            self._i_th = max(-self.integral_limit, min(self.integral_limit, self._i_th))
+            th = (
+                self.kp_throttle * err
+                + self.ki_throttle * self._i_th
+                + self.kd_throttle * d_err
+            )
+            th = clamp01(th)
+            br = 0.0
+            self._i_br = 0.0
+        elif err < -self.deadband_kph:
+            self._i_br = clamp01(self._i_br - err * dt)  # nota: err negativo
+            self._i_br = max(-self.integral_limit, min(self.integral_limit, self._i_br))
+            br = (
+                self.kp_brake * (-err)
+                + self.ki_brake * self._i_br
+                + self.kd_brake * (-d_err)
+            )
+            br = clamp01(br)
+            th = 0.0
+            self._i_th = 0.0
+        else:
+            self._i_th *= 0.9
+            self._i_br *= 0.9
+
+        return th, br
+
+
+__all__ = ["SplitPID", "clamp01"]
+
*** End Patch
```

### 3) `tools/apply_frenada_v0.py`
```diff
*** Begin Patch
*** Add File: tools/apply_frenada_v0.py
+from __future__ import annotations
+
+"""Aplica Frenada v0 offline para generar columnas: target_speed_kph, phase.
+
+Inputs por defecto:
+  - data/run.csv           (telemetría con t_wall y speed_kph)
+  - data/run.dist.csv      (columna dist_next_limit_m, t_wall)
+  - data/events.jsonl      (eventos con getdata_next_limit.kph y t_wall)
+
+Salida:
+  - data/run.ctrl.csv      (merge con columnas nuevas)
+"""
+
+import argparse
+import json
+from pathlib import Path
+from typing import Any, Dict, List, Optional
+
+import pandas as pd
+
+from runtime.braking_v0 import BrakingConfig, compute_target_speed_kph
+
+
+def _load_next_limit_series(events_path: Path) -> pd.DataFrame:
+    rows: List[Dict[str, Any]] = []
+    if not events_path.exists():
+        return pd.DataFrame(columns=["t_wall", "next_limit_kph"])  # vacío
+
+    with events_path.open("r", encoding="utf-8") as f:
+        for line in f:
+            try:
+                obj = json.loads(line)
+            except Exception:
+                continue
+            t_wall = obj.get("t_wall")
+            if t_wall is None:
+                continue
+            if obj.get("type") == "getdata_next_limit":
+                kph = obj.get("kph") or obj.get("speed_kph") or obj.get("limit_kph")
+                if kph is not None:
+                    rows.append({"t_wall": float(t_wall), "next_limit_kph": float(kph)})
+
+    df = pd.DataFrame(rows).sort_values("t_wall")
+    return df
+
+
+def main() -> None:
+    p = argparse.ArgumentParser()
+    p.add_argument("--log", default="data/run.csv")
+    p.add_argument("--dist", default="data/run.dist.csv")
+    p.add_argument("--events", default="data/events.jsonl")
+    p.add_argument("--out", default="data/run.ctrl.csv")
+    p.add_argument("--margin-kph", type=float, default=3.0)
+    p.add_argument("--A", type=float, default=0.7, help="Deceleración de servicio (m/s^2)")
+    p.add_argument("--reaction", type=float, default=0.6)
+    args = p.parse_args()
+
+    log = pd.read_csv(args.log)
+    if "t_wall" not in log.columns:
+        raise SystemExit("run.csv debe contener columna t_wall en segundos unix")
+    if "speed_kph" not in log.columns:
+        raise SystemExit("run.csv debe contener speed_kph")
+
+    dist = pd.read_csv(args.dist)
+    if "dist_next_limit_m" not in dist.columns:
+        raise SystemExit("run.dist.csv debe contener dist_next_limit_m")
+
+    # Merge por t_wall (nearest dentro de 0.2s)
+    merged = pd.merge_asof(
+        log.sort_values("t_wall"),
+        dist.sort_values("t_wall"),
+        on="t_wall",
+        direction="nearest",
+        tolerance=0.2,
+    )
+
+    next_lim = _load_next_limit_series(Path(args.events))
+    if len(next_lim):
+        merged = pd.merge_asof(
+            merged.sort_values("t_wall"),
+            next_lim.sort_values("t_wall"),
+            on="t_wall",
+            direction="backward",
+            tolerance=5.0,
+        )
+    else:
+        merged["next_limit_kph"] = merged.get("limit_kph", pd.Series([None] * len(merged)))
+
+    cfg = BrakingConfig(margin_kph=args.margin_kph, max_service_decel=args.A, reaction_time_s=args.reaction)
+
+    tgt: List[float] = []
+    phase: List[str] = []
+    for v_now, d, lim in zip(merged["speed_kph"].values, merged["dist_next_limit_m"].values, merged["next_limit_kph"].values):
+        v_t, ph = compute_target_speed_kph(float(v_now), None if pd.isna(lim) else float(lim), None if pd.isna(d) else float(d), cfg=cfg)
+        tgt.append(v_t)
+        phase.append(ph)
+
+    merged["target_speed_kph"] = tgt
+    merged["phase"] = phase
+
+    out_path = Path(args.out)
+    out_path.parent.mkdir(parents=True, exist_ok=True)
+    merged.to_csv(out_path, index=False)
+    print(f"Escrito {out_path} ({len(merged)} filas)")
+
+
+if __name__ == "__main__":
+    main()
+
*** End Patch
```

### 4) `tests/test_braking_v0.py`
```diff
*** Begin Patch
*** Add File: tests/test_braking_v0.py
+from __future__ import annotations
+
+from runtime.braking_v0 import BrakingConfig, compute_target_speed_kph
+
+
+def test_braking_targets_decrease_with_distance():
+    cfg = BrakingConfig(margin_kph=3.0, max_service_decel=0.7)
+    # 120→80 a 1000m debe permitir > a 100m
+    v1, _ = compute_target_speed_kph(120.0, 80.0, 1000.0, cfg=cfg)
+    v2, _ = compute_target_speed_kph(120.0, 80.0, 100.0, cfg=cfg)
+    assert v1 >= v2
+
+
+def test_braking_respects_margin():
+    cfg = BrakingConfig(margin_kph=5.0, max_service_decel=1.0)
+    v, _ = compute_target_speed_kph(90.0, 80.0, 0.0, cfg=cfg)
+    assert v <= 75.0 + 0.1
+
+
+def test_no_limit_returns_current():
+    cfg = BrakingConfig()
+    v, phase = compute_target_speed_kph(70.0, None, 500.0, cfg=cfg)
+    assert v == 70.0 and phase == "CRUISE"
+
*** End Patch
```

### 5) `tests/test_pid.py`
```diff
*** Begin Patch
*** Add File: tests/test_pid.py
+from __future__ import annotations
+
+from runtime.pid import SplitPID
+
+
+def test_split_pid_signs():
+    pid = SplitPID(kp_throttle=0.1, kp_brake=0.2)
+    th, br = pid.update(100.0, 90.0, dt=0.1)
+    assert th > 0.0 and br == 0.0
+    th, br = pid.update(80.0, 90.0, dt=0.1)
+    assert br > 0.0 and th == 0.0
+
*** End Patch
```

---

## Cambios en archivos EXISTENTES

### `tools/plot_run.py` (añadir trazas si existen)
```diff
*** Begin Patch
*** Update File: tools/plot_run.py
@@
-    ax.plot(df["speed_kph"], label="speed_kph")
+    ax.plot(df["speed_kph"], label="speed_kph")
+    if "target_speed_kph" in df.columns:
+        ax.plot(df["target_speed_kph"], label="target_speed_kph", linestyle=":")
+    if "dist_next_limit_m" in df.columns:
+        ax2 = ax.twinx()
+        ax2.plot(df["dist_next_limit_m"], label="dist_next_limit_m")
+        ax2.set_ylabel("m")
+    if "phase" in df.columns:
+        # marcas simples por fase
+        for idx, ph in df["phase"].dropna().items():
+            if ph == "BRAKE":
+                ax.axvline(idx, alpha=0.1)
*** End Patch
```

> Nota: el bloque `@@` puede variar según tu versión; el parche es aditivo y seguro (solo usa columnas si existen).

---

## Cómo ejecutar

1) Generar `run.ctrl.csv` con las columnas nuevas:
```powershell
python -m tools.apply_frenada_v0 --log data/run.csv --dist data/run.dist.csv --events data/events.jsonl --out data/run.ctrl.csv --A 0.7 --margin-kph 3 --reaction 0.6
```

2) Plot rápido (mostrará `target_speed_kph` y `dist_next_limit_m` si existen):
```powershell
python -m tools.plot_run data/run.ctrl.csv
```

3) Tests:
```powershell
pytest -q
```

---

## Integración online (opcional rápida)
En tu bucle de control actual, importa y usa:

```python
from runtime.braking_v0 import compute_target_speed_kph, BrakingConfig
from runtime.pid import SplitPID

cfg = BrakingConfig()
pid = SplitPID()
# ... en cada tick (dt):
v_obj, fase = compute_target_speed_kph(v_now_kph, next_limit_kph, dist_next_limit_m, cfg=cfg)
th, br = pid.update(v_obj, v_now_kph, dt)
# aplicar th/br según backend real o TSC_FAKE_RD
```

---

## Siguientes pasos sugeridos
- Exponer `A` (deceleración) por **vehículo** (CSV/JSON por loco) y autotune con datos reales.
- Añadir `overspeed_guard`: si `speed_kph > next_limit_kph + 1.5`, priorizar freno.
- Loggear `v_obj`, `fase`, `th`, `br` en el CSV para análisis (colaboro en parche cuando confirmes rutas exactas del logger).
