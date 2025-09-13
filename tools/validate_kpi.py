from __future__ import annotations
import argparse
import sys
from pathlib import Path
from typing import Tuple, Dict, List
import pandas as pd
import numpy as np

def _choose_col(df: pd.DataFrame, candidates: List[str], name: str) -> str:
    for c in candidates:
        if c in df.columns:
            return c
    raise SystemExit(f"[validate_kpi] No se encontró columna '{name}'. Prueba con --{name.replace('_','-')}-col")

def _segments_by_limit(df: pd.DataFrame, limit_col: str) -> List[Tuple[int, int]]:
    """Devuelve segmentos [i0,i1) donde el valor de 'limit_col' es constante y hay datos de distancia."""
    idx = df.index[df[limit_col].notna()].to_list()
    if not idx:
        return []
    segs = []
    start = idx[0]
    prev_lim = df.loc[start, limit_col]
    for i in idx[1:]:
        cur_lim = df.loc[i, limit_col]
        if cur_lim != prev_lim or i != (segs[-1][1] if segs else start) + 1:
            # corte por cambio de límite o ruptura no contigua
            segs.append((start, i))
            start = i
            prev_lim = cur_lim
    segs.append((start, idx[-1] + 1))
    return segs

def compute_kpis(
    df: pd.DataFrame,
    dist_col: str = "dist_next_limit_m",
    limit_col: str = "next_limit_kph",
    v_col: str = "v_kmh",
    arrival_dist_m: float = 8.0,
    arrival_vmargin_kph: float = 0.5,
    window_m: float = 50.0,
    bump_thresh_m: float = 2.0,
) -> Dict[str, float]:
    # Column picking / coercion
    v_col = v_col or _choose_col(df, ["v_kmh","v_kph","speed_kph","speed_kmh"], "v_col")
    limit_col = limit_col or _choose_col(df, ["next_limit_kph","limit_next_kph","next_limit"], "limit_col")
    dist_col = dist_col or _choose_col(df, ["dist_next_limit_m","next_limit_dist_m","dist_next_limit"], "dist_col")
    for c in (v_col, limit_col, dist_col):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[[v_col, limit_col, dist_col]].dropna().copy()
    if df.empty:
        raise SystemExit("[validate_kpi] CSV sin datos útiles tras limpieza.")

    # --- 1) Monotonicidad: subidas (> bump_thresh_m) mientras el 'limit_col' es constante
    bumps = 0
    segs = _segments_by_limit(df, limit_col)
    for i0, i1 in segs:
        d = df.iloc[i0:i1][dist_col].to_numpy()
        dd = np.diff(d)
        bumps += int(np.sum(dd > bump_thresh_m))

    # --- 2) Margen medio últimos 'window_m' metros (v - limit) con 0 <= dist <= window_m
    win = df[(df[dist_col] >= 0) & (df[dist_col] <= window_m)].copy()
    mean_margin_last50 = float((win[v_col] - win[limit_col]).mean()) if not win.empty else float("nan")

    # --- 3) Arrivals OK: detectar cruces al umbral 'arrival_dist_m' y evaluar velocidad
    # Evento: una muestra entra en [0, arrival_dist_m] desde > arrival_dist_m.
    arrivals, ok = 0, 0
    dist = df[dist_col].to_numpy()
    v = df[v_col].to_numpy()
    lim = df[limit_col].to_numpy()
    for i in range(1, len(df)):
        if dist[i-1] > arrival_dist_m >= dist[i]:
            arrivals += 1
            # Ventana corta desde i hacia adelante mientras dist crece desde 0 hasta arrival_dist_m
            j = i
            best_ok = False
            while j < len(df) and 0 <= dist[j] <= arrival_dist_m:
                if v[j] <= lim[j] + arrival_vmargin_kph:
                    best_ok = True
                    break
                j += 1
            ok += int(best_ok)
    arrivals_ok = (ok / arrivals) if arrivals > 0 else float("nan")

    return {
        "arrivals": float(arrivals),
        "arrivals_ok": float(arrivals_ok) if arrivals_ok == arrivals_ok else float("nan"),
        "monotonicity_bumps": float(bumps),
        "mean_margin_last50_kph": float(mean_margin_last50) if mean_margin_last50 == mean_margin_last50 else float("nan"),
    }

def main():
    p = argparse.ArgumentParser(description="Validador KPI v0 para TrainSimAI")
    p.add_argument("--csv", required=True, help="Ruta al CSV de control (p.ej. data\\runs\\ctrl_live_XXXX.csv)")
    p.add_argument("--dist-col", default="dist_next_limit_m")
    p.add_argument("--limit-col", default="next_limit_kph")
    p.add_argument("--v-col", default="v_kmh")
    p.add_argument("--arrival-dist-m", type=float, default=8.0)
    p.add_argument("--arrival-vmargin-kph", type=float, default=0.5)
    p.add_argument("--window-m", type=float, default=50.0)
    p.add_argument("--monotonicity-bump-m", type=float, default=2.0)
    # Umbrales de aceptación (puedes cambiarlos en CLI)
    p.add_argument("--min-arrivals-ok", type=float, default=0.90)
    p.add_argument("--max-bumps", type=int, default=0)
    p.add_argument("--target-margin-min", type=float, default=0.5)
    p.add_argument("--target-margin-max", type=float, default=1.0)
    args = p.parse_args()

    path = Path(args.csv)
    if not path.exists():
        raise SystemExit(f"[validate_kpi] No existe: {path}")
    df = pd.read_csv(path)
    k = compute_kpis(
        df,
        dist_col=args.dist_col,
        limit_col=args.limit_col,
        v_col=args.v_col,
        arrival_dist_m=args.arrival_dist_m,
        arrival_vmargin_kph=args.arrival_vmargin_kph,
        window_m=args.window_m,
        bump_thresh_m=args.monotonicity_bump_m,
    )
    # Informe resumido
    print(f"[KPI] arrivals={int(k['arrivals'])}  arrivals_ok={k['arrivals_ok']:.3f}  "
          f"mean_margin_last50_kph={k['mean_margin_last50_kph']:.3f}  "
          f"monotonicity_bumps={int(k['monotonicity_bumps'])}")

    ok = True
    if k["arrivals_ok"] != k["arrivals_ok"] or k["arrivals_ok"] < args.min_arrivals_ok:
        print(f"[KPI][FAIL] arrivals_ok < {args.min_arrivals_ok:.2f}")
        ok = False
    if k["monotonicity_bumps"] > args.max_bumps:
        print(f"[KPI][FAIL] monotonicity_bumps > {args.max_bumps}")
        ok = False
    if not (args.target_margin_min <= k["mean_margin_last50_kph"] <= args.target_margin_max):
        print(f"[KPI][WARN] mean_margin_last50_kph fuera del objetivo [{args.target_margin_min},{args.target_margin_max}] (no bloquea)")
    sys.exit(0 if ok else 2)

if __name__ == "__main__":
    main()
