from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from typing import Optional, List, Tuple

import numpy as np
import pandas as pd

RUNS_DIR = Path("data/runs")
EVENTS_PATH = Path("data/events/events.jsonl")


def latest_csv(runs_dir: Path = RUNS_DIR) -> Path:
    csvs = sorted(runs_dir.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not csvs:
        raise FileNotFoundError(f"No se encontraron CSV en {runs_dir}")
    return csvs[0]


def read_events(path: Path = EVENTS_PATH) -> list[dict]:
    out: list[dict] = []
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


# Preferir distancias directas de getdata_next_limit si existen en events.jsonl
def _load_events_jsonl(path: Path) -> list[dict]:
    ev: list[dict] = []
    if not path.exists():
        return ev
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return ev


def dist_from_getdata_probes(df: pd.DataFrame, ev_path: Path) -> Optional[pd.Series]:
    """
    Construye una serie dist_next_limit_m alineada con df a partir de eventos
    normalizados getdata_next_limit (que traen meta.dist_m).
    Requiere que df tenga 't_wall' (float) y que events.jsonl haya sido normalizado.
    """
    events = _load_events_jsonl(ev_path)
    rows: list[dict] = []
    for e in events:
        if str(e.get("type")) != "getdata_next_limit":
            continue
        t = e.get("t_wall")
        meta = e.get("meta") or {}
        dist = meta.get("dist_m")
        if isinstance(t, (int, float)) and isinstance(dist, (int, float)):
            rows.append({"t_wall": float(t), "dist_m": float(dist)})
    if not rows:
        return None
    probes = (
        pd.DataFrame(rows)
        .sort_values("t_wall")
        .drop_duplicates(subset=["t_wall"], keep="last")
    )
    if "t_wall" not in df.columns or df["t_wall"].isna().all():
        return None
    # Alinear por tiempo real con merge_asof (sample&hold)
    s = pd.merge_asof(
        df[["t_wall"]].sort_values("t_wall"),
        probes,
        on="t_wall",
        direction="backward",
        allow_exact_matches=True,
    )["dist_m"]
    s.index = df.index  # restaurar índice original
    return s


def pick_series(df: pd.DataFrame, *candidates: str) -> Optional[pd.Series]:
    for name in candidates:
        if name in df.columns:
            return df[name]
    return None


def ensure_odom(df: pd.DataFrame) -> pd.Series:
    """
    Devuelve una serie odom_m. Si no existe, integra v para estimarla.
    Requiere t_wall (o t) y velocidad (kph o m/s).
    """
    odom = pick_series(df, "odom_m", "distance_m", "odom")
    if odom is not None:
        return odom.astype(float)

    t = pick_series(df, "t_wall", "time_wall_s", "time", "t")
    if t is None:
        # fallback: índice ~ dt constante
        t = pd.Series(np.arange(len(df)), index=df.index, name="t_fallback")
    t = t.astype(float)

    v_ms_series = pick_series(df, "v_ms", "speed_ms")
    if v_ms_series is None:
        v_kph = pick_series(df, "speed_kph", "kph", "speed_kmh")
        if v_kph is not None:
            v_ms_series = (v_kph.astype(float) / 3.6)
    if v_ms_series is None:
        raise ValueError("No hay odom_m ni velocidad para integrarla (esperaba speed_kph/v_ms).")
    v_arr = v_ms_series.astype(float).fillna(0.0).to_numpy()

    t_arr = t.ffill().bfill().to_numpy(dtype=float)
    dt = np.diff(t_arr, prepend=t_arr[0])
    # Si el primer dt es 0 (por prepend), ignóralo
    dt[0] = 0.0
    odom_est = np.cumsum(v_arr * dt)
    return pd.Series(odom_est, index=df.index, name="odom_m")


def extract_limit_events(events: list[dict]) -> Tuple[np.ndarray, np.ndarray]:
    """
    Devuelve (event_odom_m, event_next_limit_kph) ordenados por odómetro.
    Usa odom_m del evento si está; si no, intenta casar por tiempo (t_wall/t_game) → se resolverá en el llamador.
    Aquí solo filtramos y recogemos 'next'/'to' si existen.
    """
    e_odom: List[float] = []
    e_next: List[float] = []
    for ev in events:
        if str(ev.get("type")) != "speed_limit_change":
            continue
        # posibles ubicaciones del nuevo límite
        next_lim = None
        meta = ev.get("meta") or {}
        for k in ("next", "to", "limit_next_kph"):
            if k in ev:
                next_lim = ev[k]
                break
            if k in meta:
                next_lim = meta[k]
                break
        od = ev.get("odom_m")
        if od is None:
            # marcador NaN: se resolverá fuera (matching por tiempo)
            e_odom.append(np.nan)
        else:
            e_odom.append(float(od))
        e_next.append(float(next_lim) if next_lim is not None else np.nan)
    if not e_odom:
        return np.array([]), np.array([])
    e_odom_arr = np.asarray(e_odom, dtype=float)
    e_next_arr = np.asarray(e_next, dtype=float)
    # Mantener orden original; el orden por odómetro se aplicará
    # tras resolver NaN en el llamador
    return e_odom_arr, e_next_arr


def match_events_without_odom(
    e_odom: np.ndarray,
    df_t: pd.Series,
    df_odom: pd.Series,
    events: list[dict],
) -> np.ndarray:
    """
    Rellena odómetros faltantes en e_odom casando por tiempo: usa t_wall o t_game del evento
    y toma el odómetro de la fila más cercana en el CSV.
    """
    if not len(events):
        return e_odom
    t_arr = df_t.to_numpy(dtype=float, copy=False)
    out = e_odom.copy()
    limit_events = [e for e in events if str(e.get("type")) == "speed_limit_change"]
    for i, ev in enumerate(limit_events):
        if not np.isnan(out[i]):
            continue
        te = None
        for k in ("t_wall", "t_game", "t_ingame", "time"):
            if k in ev and ev[k] is not None:
                te = float(ev[k])
                break
        if te is None:
            continue
        idx = int(np.argmin(np.abs(t_arr - te)))
        out[i] = float(df_odom.iloc[idx])
    return out


def compute_distances(
    df: pd.DataFrame,
    events: list[dict],
) -> Tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """
    Devuelve (df_out, e_odom_resueltos, e_next_kph) donde df_out incluye:
      - dist_next_limit_m
      - next_limit_kph (si disponible)
    """
    # tiempo preferente para matching
    t = pick_series(df, "t_wall", "time_wall_s", "time", "t")
    if t is None:
        t = pd.Series(np.arange(len(df)), index=df.index, name="t_fallback")
    t = t.astype(float)

    odom = ensure_odom(df)

    e_odom, e_next = extract_limit_events(events)
    if e_odom.size == 0:
        # no hay eventos: dist = NaN
        df_out = df.copy()
        df_out["dist_next_limit_m"] = np.nan
        df_out["next_limit_kph"] = np.nan
        return df_out, e_odom, e_next

    # Resolver odómetros faltantes por matching temporal
    e_odom_res = match_events_without_odom(e_odom, t, odom, events)

    # Ordenar definitivamente por odómetro
    order = np.argsort(e_odom_res)
    e_odom_res = e_odom_res[order]
    e_next = e_next[order]

    x = odom.to_numpy(dtype=float, copy=False)
    idx = np.searchsorted(e_odom_res, x, side="right")
    has_next = idx < e_odom_res.size
    dist = np.full_like(x, np.nan)
    dist[has_next] = e_odom_res[idx[has_next]] - x[has_next]

    next_lim = np.full_like(x, np.nan)
    next_lim[has_next] = e_next[idx[has_next]]

    df_out = df.copy()
    df_out["dist_next_limit_m"] = dist
    df_out["next_limit_kph"] = next_lim
    return df_out, e_odom_res, e_next


def main() -> None:
    ap = argparse.ArgumentParser(description="Añade dist_next_limit_m al último run.")
    ap.add_argument("--run", type=str, default="", help="Ruta al CSV del run (por defecto, último en data/runs/)")
    ap.add_argument("--events", type=str, default=str(EVENTS_PATH), help="Ruta a events.jsonl")
    ap.add_argument("--out", type=str, default="", help="Archivo de salida (por defecto, <run>.dist.csv)")
    ap.add_argument(
        "--no-overwrite",
        action="store_true",
        help="Si el run ya es .dist.csv, escribe <base>.dist2.csv en vez de sobrescribir",
    )
    args = ap.parse_args()

    run_path = Path(args.run) if args.run else latest_csv()
    ev_path = Path(args.events)
    if args.out:
        out_path = Path(args.out)
    else:
        # Normaliza el nombre: quita .csv y TODAS las colas .dist / .distN (case-insensitive)
        stem = run_path.name
        stem_no_csv = stem[:-4] if stem.lower().endswith(".csv") else stem
        root = re.sub(r"(?:\.dist\d*)+$", "", stem_no_csv, flags=re.IGNORECASE)
        had_dist = (root != stem_no_csv)
        target = root + (".dist2.csv" if (had_dist and args.no_overwrite) else ".dist.csv")
        out_path = run_path.with_name(target)

    # Detectar delimitador automáticamente (nuestros CSV suelen ser ';')
    df = pd.read_csv(run_path, sep=None, engine="python")
    events = read_events(ev_path)
    # 1) Cálculo existente por eventos de límite y odómetro
    df_out, _, _ = compute_distances(df, events)
    # 2) Si hay probes getdata_next_limit con distancias, preferirlos
    try:
        s_probe = dist_from_getdata_probes(df_out, ev_path)
    except Exception:
        s_probe = None
    if s_probe is not None and not s_probe.isna().all():
        col = "dist_next_limit_m"
        if col not in df_out.columns:
            df_out[col] = np.nan
        df_out[col] = s_probe.combine_first(df_out[col])
    df_out.to_csv(out_path, index=False)
    print(f"[dist] OK → {out_path}")


if __name__ == "__main__":
    main()
