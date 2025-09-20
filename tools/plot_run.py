#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""
plot_run.py — Gráfico rápido (MVP)
Lee:
- data/runs/run.csv           (CSV ; con v_kmh/speed_kph, odom_m, time_ingame_{h,m,s})
- data/events/events.jsonl    (eventos normalizados)
Opcionalmente traza señales de control (throttle/brake) y marcas por fase (phase).

Uso:
  python tools/plot_run.py
  python tools/plot_run.py --run data/runs/run.csv --events data/events/events.jsonl --out plot_speed_vs_odom.png
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from typing import List, Dict, Any, Optional, Sequence, Mapping, Tuple
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # sin GUI


def _detect_delimiter(sample: str) -> str:
    return ";" if sample.count(";") >= sample.count(",") else ","


def read_run_csv(path: str) -> Dict[str, List[Any]]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"No existe CSV: {path}")
    try:
        csv.field_size_limit(50 * 1024 * 1024)
    except Exception:
        pass
    t_ing: List[Optional[float]] = []
    v_kmh: List[Optional[float]] = []
    odom: List[Optional[float]] = []
    throttle: List[Optional[float]] = []
    brake: List[Optional[float]] = []
    phase: List[Optional[str]] = []
    with open(path, "r", encoding="utf-8", errors="ignore", newline="") as f:
        sample = f.read(4096)
        delim = _detect_delimiter(sample)
        f.seek(0)
        r = csv.DictReader(f, delimiter=delim)
        for row in r:
            # tiempo in-game -> horas decimales (si existen columnas)
            try:
                H = float(row.get("time_ingame_h") or 0.0)
                M = float(row.get("time_ingame_m") or 0.0)
                S = float(row.get("time_ingame_s") or 0.0)
                tg = H + M / 60.0 + S / 3600.0
            except Exception:
                tg = None
            t_ing.append(tg)
            # velocidad
            try:
                vk = float(row.get("v_kmh") or (row.get("SpeedometerKPH") or 0.0) or (row.get("speed_kph") or 0.0))
            except Exception:
                vk = None
            v_kmh.append(vk)
            # odómetro
            try:
                om = float(row.get("odom_m") or 0.0)
            except Exception:
                om = None
            odom.append(om)
            # señales opcionales del controlador
            try:
                th = row.get("throttle")
                throttle.append(float(th) if th not in (None, "") else None)
            except Exception:
                throttle.append(None)
            try:
                br = row.get("brake")
                brake.append(float(br) if br not in (None, "") else None)
            except Exception:
                brake.append(None)
            ph = row.get("phase")
            phase.append(ph if ph not in (None, "") else None)
    return {
        "t_ing": t_ing,
        "v_kmh": v_kmh,
        "odom": odom,
        "throttle": throttle,
        "brake": brake,
        "phase": phase,  # Optional[str]
    }


def read_events(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"No existe JSONL: {path}")
    out = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def nearest_idx(seq: Sequence[Optional[float]], val: float) -> int:
    best_i, best_d = -1, float("inf")
    for i, x in enumerate(seq):
        if x is None:
            continue
        d = abs(x - val)
        if d < best_d:
            best_d, best_i = d, i
    return best_i


def build_event_table(events: List[Dict[str, Any]], run: Mapping[str, List[Optional[float]]]) -> List[Dict[str, Any]]:
    table = []
    for e in events:
        t = e.get("t_ingame") or e.get("time")
        i = nearest_idx(run["t_ing"], float(t)) if t is not None else -1
        od = run["odom"][i] if i >= 0 else None
        vk = run["v_kmh"][i] if i >= 0 else None
        row = {"type": e.get("type"), "t_ingame": t, "odom_m": od, "v_kmh_at_evt": vk}
        if e.get("type") == "speed_limit_change":
            row["limit_prev_kmh"] = e.get("limit_prev_kmh")
            row["limit_next_kmh"] = e.get("limit_next_kmh")
        elif e.get("type") == "limit_reached":
            row["limit_kmh"] = e.get("limit_kmh")
            row["dist_m_travelled"] = e.get("dist_m_travelled")
        elif e.get("type") == "marker_pass":
            row["marker"] = e.get("marker")
        elif e.get("type") in ("stop_begin", "stop_end"):
            row["station"] = e.get("station")
        table.append(row)
    return table


def _clean_xy(
    x_seq: Sequence[Optional[float]],
    y_seq: Sequence[Optional[float]],
) -> Tuple[List[float], List[float]]:
    """Filtra None/NaN y devuelve listas seguras para matplotlib."""
    xs: List[float] = []
    ys: List[float] = []
    for xv, yv in zip(x_seq, y_seq):
        if xv is None or yv is None:
            continue
        # evita NaN
        if isinstance(xv, float) and math.isnan(xv):
            continue
        if isinstance(yv, float) and math.isnan(yv):
            continue
        try:
            xs.append(float(xv))
            ys.append(float(yv))
        except Exception:
            continue
    return xs, ys


def _ensure_parent_dir(path: str) -> str:
    """Crea el directorio padre del path si no existe y devuelve el path."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return str(p)


def plot_speed_vs_odom(run: Mapping[str, List[Optional[float]]], evtable: List[Dict[str, Any]], out_path: str) -> None:
    import matplotlib.pyplot as plt

    xs, ys, idxs = [], [], []
    for i, om in enumerate(run["odom"]):
        if om is None or run["v_kmh"][i] is None:
            continue
        xs.append(om)
        ys.append(run["v_kmh"][i])
        idxs.append(i)
    if not xs or not ys:
        raise RuntimeError("No hay datos de odómetro/velocidad para graficar.")

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(xs, ys, label="v_kmh")
    ymax = max(ys) if ys else 1.0
    for r in evtable:
        x = r.get("odom_m")
        if x is None:
            continue
        t = r.get("type")
        if t == "speed_limit_change":
            ax.axvline(x, linestyle="--", alpha=0.7)
            ax.text(x, ymax * 0.95, f"limit→{r.get('limit_next_kmh')}", rotation=90, va="top", ha="right", fontsize=8)
        elif t == "limit_reached":
            ax.axvline(x, linestyle=":", alpha=0.7)
            ax.text(x, ymax * 0.80, f"reached {r.get('limit_kmh')}", rotation=90, va="top", ha="right", fontsize=8)
        elif t == "marker_pass":
            ax.axvline(x, linestyle="-.", alpha=0.5)
            ax.text(
                x,
                ymax * 0.60,
                f"M:{r.get('marker', '')}",
                rotation=90,
                va="top",
                ha="right",
                fontsize=7,
            )

    # marcas por fase (si run incluye 'phase')
    try:
        if any(run.get("phase", [])):
            for i in idxs:
                ph = run.get("phase", [None] * len(run["odom"]))[i]
                if (ph or "").upper() == "BRAKE":
                    ax.axvline(run["odom"][i], color="red", alpha=0.08)
    except Exception:
        pass

    # Eje secundario para throttle/brake
    ax2 = None
    has_th = any(v is not None for v in run.get("throttle", []))
    has_br = any(v is not None for v in run.get("brake", []))
    if has_th or has_br:
        ax2 = ax.twinx()
        ctrl_x, th_y, br_y = [], [], []
        for i in idxs:
            ctrl_x.append(run["odom"][i])
            th_y.append(run.get("throttle", [None] * len(run["odom"]))[i])
            br_y.append(run.get("brake", [None] * len(run["odom"]))[i])
        if has_th:
            ax2.plot(ctrl_x, th_y, label="throttle", color="tab:green", alpha=0.7)
        if has_br:
            ax2.plot(ctrl_x, br_y, label="brake", color="tab:red", alpha=0.7)
        ax2.set_ylabel("ctrl 0..1")
        h1, lab1 = ax.get_legend_handles_labels()
        h2, lab2 = ax2.get_legend_handles_labels()
        ax.legend(h1 + h2, lab1 + lab2, loc="upper right")
    else:
        ax.legend(loc="upper right")

    # Si existen columnas diagnósticas, añadirlas
    # speed_filt_kph traza la velocidad filtrada usada por el lazo de control
    if "speed_filt_kph" in run:
        try:
            sf_x, sf_y = [], []
            for i, om in enumerate(run["odom"]):
                if om is None:
                    continue
                sf = run.get("speed_filt_kph", [None] * len(run["odom"]))[i]
                if sf is None:
                    continue
                sf_x.append(om)
                sf_y.append(sf)
            if sf_x:
                ax.plot(sf_x, sf_y, label="speed_filt_kph", linestyle="--", alpha=0.6)
        except Exception:
            pass

    # Si hay active_limit_kph, lo dibujamos en eje Y secundario (señal de límite en vigor)
    if "active_limit_kph" in run:
        try:
            if ax2 is None:
                ax2 = ax.twinx()
            al_x, al_y = [], []
            for i, om in enumerate(run["odom"]):
                if om is None:
                    continue
                al = run.get("active_limit_kph", [None] * len(run["odom"]))[i]
                if al is None or al == "":
                    continue
                al_x.append(om)
                al_y.append(float(al))
            if al_x:
                ax2.plot(al_x, al_y, label="active_limit_kph", alpha=0.35)
                ax2.set_ylabel("active_limit_kph")
                # leyenda combinada (manera tipada y compatible con Pylance/Ruff)
                h1, lab1 = ax.get_legend_handles_labels()
                h2, lab2 = ax2.get_legend_handles_labels()
                ax.legend(h1 + h2, lab1 + lab2, loc="upper left")
        except Exception:
            pass

    # Sombreado (axvspan) para zonas donde approach_active=1
    if "approach_active" in run:
        try:
            mask = [int(x) if x not in (None, "") else 0 for x in run.get("approach_active", [0] * len(run["odom"]))]
            s = None
            for i, m in enumerate(mask):
                if m and s is None:
                    s = i
                if (not m or i == len(mask) - 1) and s is not None:
                    e = i if not m else i
                    # mapear índice a coordenada de odómetro (si disponible)
                    try:
                        raw0 = run["odom"][s]
                        raw1 = run["odom"][e]
                        x0 = None
                        x1 = None
                        if raw0 is not None and not (isinstance(raw0, float) and math.isnan(raw0)):
                            x0 = float(raw0)
                        if raw1 is not None and not (isinstance(raw1, float) and math.isnan(raw1)):
                            x1 = float(raw1)
                        # fallback a índices si no hay coordenadas de odómetro válidas
                        if x0 is None:
                            x0 = float(s)
                        if x1 is None:
                            x1 = float(e)
                        ax.axvspan(x0, x1, alpha=0.08, color="gray")
                    except Exception:
                        pass
                    s = None
        except Exception:
            pass

    ax.set_xlabel("odom_m")
    ax.set_ylabel("v_kmh")
    ax.set_title("Velocidad vs Odómetro (con eventos)")
    fig.tight_layout()
    out_path = _ensure_parent_dir(out_path)
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def plot_speed_vs_index_df(df, out_path: str) -> None:
    """Plot usando un DataFrame (índice como eje X). Añade trazas diagnósticas si existen.
    Esta función no modifica el comportamiento legado; es opcional via --pandas.
    """
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(12, 6))
    # curvas principales
    ax.plot(df.index, df["speed_kph"], label="speed_kph")
    if "target_speed_kph" in df.columns:
        ax.plot(df.index, df["target_speed_kph"], label="target_speed_kph")
    if "speed_filt_kph" in df.columns:
        ax.plot(df.index, df["speed_filt_kph"], label="speed_filt_kph", linestyle="--", alpha=0.6)

    # active_limit en eje secundario
    if "active_limit_kph" in df.columns:
        ax2 = ax.twinx()
        ax2.plot(df.index, df["active_limit_kph"], label="active_limit_kph", alpha=0.35)
        ax2.set_ylabel("active_limit_kph")
        h1, lab1 = ax.get_legend_handles_labels()
        h2, lab2 = ax2.get_legend_handles_labels()
        ax.legend(h1 + h2, lab1 + lab2, loc="upper left")

    # sombreado para approach_active (índices)
    if "approach_active" in df.columns:
        try:
            mask = df["approach_active"].fillna(0).astype(int).values
            s = None
            for i, m in enumerate(mask):
                if m and s is None:
                    s = i
                if (not m or i == len(mask) - 1) and s is not None:
                    e = i if not m else i
                    ax.axvspan(s, e, alpha=0.08, color="gray")
                    s = None
        except Exception:
            pass

    ax.set_xlabel("index")
    ax.set_ylabel("speed_kph")
    ax.set_title("Velocidad (índice) — con señales de control y approach")
    fig.tight_layout()
    out_path = _ensure_parent_dir(out_path)
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def save_events_csv(evtable, out_csv):
    if not evtable:
        return
    fields = sorted(set().union(*[row.keys() for row in evtable]))
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        w.writeheader()
        for row in evtable:
            w.writerow(row)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=os.path.join("data", "runs", "run.csv"))
    ap.add_argument("--events", default=os.path.join("data", "events", "events.jsonl"))
    ap.add_argument("--out", default="plot_speed_vs_odom.png")
    ap.add_argument("--pandas", action="store_true", help="Usar pandas DataFrame como fuente y trazado alternativo")
    ap.add_argument("--events-out-csv", default="events_timeline.csv")
    args = ap.parse_args()
    run = read_run_csv(args.run)
    events = read_events(args.events)
    evtable = build_event_table(events, run)
    if getattr(args, "pandas", False):
        try:
            import pandas as pd
        except Exception:
            raise RuntimeError("Se solicitó --pandas pero no está disponible 'pandas' en el entorno")
        # construir DataFrame simple (index incremental)
        df = pd.DataFrame(run)
        df.index = pd.RangeIndex(start=0, stop=len(df))
        # Normalizar nombres/formatos: algunos CSV usan 'v_kmh' en vez de 'speed_kph'
        if "speed_kph" not in df.columns and "v_kmh" in df.columns:
            df["speed_kph"] = df["v_kmh"]
        # Forzar columnas numéricas donde corresponda (coerce -> NaN si no convertible)
        for col in ("speed_kph", "target_speed_kph", "speed_filt_kph", "active_limit_kph", "approach_active"):
            if col in df.columns:
                try:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                except Exception:
                    pass
        plot_speed_vs_index_df(df, args.out)
    else:
        plot_speed_vs_odom(run, evtable, args.out)
    save_events_csv(evtable, args.events_out_csv)
    print(f"[OK] Gráfico: {args.out}")
    print(f"[OK] Timeline eventos: {args.events_out_csv}")
    print(f"[INFO] Eventos considerados: {len(evtable)}")


if __name__ == "__main__":
    main()
