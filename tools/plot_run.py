#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""
plot_run.py — Gráfico rápido (MVP)
Lee:
- data/runs/run.csv           (CSV ; con v_kmh, odom_m, time_ingame_{h,m,s})
- data/events/events.jsonl    (eventos normalizados)
Dibuja v_kmh vs odom_m con líneas en speed_limit_change / limit_reached / marker_pass.
Uso:
  python tools/plot_run.py
  python tools/plot_run.py --run data/runs/run.csv --events data/events/events.jsonl --out plot_speed_vs_odom.png
"""
import argparse
import csv
import json
import os
from typing import List, Dict, Any

import matplotlib
matplotlib.use("Agg")  # sin GUI
import matplotlib.pyplot as plt


def read_run_csv(path: str) -> Dict[str, List[float]]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"No existe CSV: {path}")
    try:
        csv.field_size_limit(50 * 1024 * 1024)
    except Exception:
        pass
    t_ing, v_kmh, odom = [], [], []
    with open(path, "r", encoding="utf-8", errors="ignore", newline="") as f:
        r = csv.DictReader(f, delimiter=";")
        for row in r:
            # tiempo in-game → horas decimales (si existen columnas)
            try:
                H = float(row.get("time_ingame_h") or 0.0)
                M = float(row.get("time_ingame_m") or 0.0)
                S = float(row.get("time_ingame_s") or 0.0)
                tg = H + M/60.0 + S/3600.0
            except Exception:
                tg = None
            t_ing.append(tg)
            # velocidad
            try:
                vk = float(row.get("v_kmh") or (row.get("SpeedometerKPH") or 0.0))
            except Exception:
                vk = None
            v_kmh.append(vk)
            # odómetro
            try:
                om = float(row.get("odom_m") or 0.0)
            except Exception:
                om = None
            odom.append(om)
    return {"t_ing": t_ing, "v_kmh": v_kmh, "odom": odom}


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


def nearest_idx(seq: List[float], val: float) -> int:
    best_i, best_d = -1, float("inf")
    for i, x in enumerate(seq):
        if x is None:
            continue
        d = abs(x - val)
        if d < best_d:
            best_d, best_i = d, i
    return best_i


def build_event_table(events: List[Dict[str, Any]], run: Dict[str, List[float]]) -> List[Dict[str, Any]]:
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
        elif e.get("type") in ("stop_begin","stop_end"):
            row["station"] = e.get("station")
        table.append(row)
    return table


def plot_speed_vs_odom(run: Dict[str, List[float]], evtable: List[Dict[str, Any]], out_path: str) -> None:
    xs, ys = [], []
    for i, om in enumerate(run["odom"]):
        if om is None or run["v_kmh"][i] is None:
            continue
        xs.append(om)
        ys.append(run["v_kmh"][i])
    if not xs or not ys:
        raise RuntimeError("No hay datos de odómetro/velocidad para graficar.")
    plt.figure(figsize=(12, 6))
    plt.plot(xs, ys, label="v_kmh")
    ymax = max(ys) if ys else 1.0
    for r in evtable:
        x = r.get("odom_m")
        if x is None:
            continue
        t = r.get("type")
        if t == "speed_limit_change":
            plt.axvline(x, linestyle="--", alpha=0.7)
            plt.text(x, ymax*0.95, f"limit→{r.get('limit_next_kmh')}", rotation=90, va="top", ha="right", fontsize=8)
        elif t == "limit_reached":
            plt.axvline(x, linestyle=":", alpha=0.7)
            plt.text(x, ymax*0.80, f"reached {r.get('limit_kmh')}", rotation=90, va="top", ha="right", fontsize=8)
        elif t == "marker_pass":
            plt.axvline(x, linestyle="-.", alpha=0.5)
            plt.text(x, ymax*0.60, f"M:{r.get('marker','')}", rotation=90, va="top", ha="right", fontsize=7)
    plt.xlabel("odom_m")
    plt.ylabel("v_kmh")
    plt.title("Velocidad vs Odómetro (con eventos)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=120)
    plt.close()


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
    ap.add_argument("--run", default=os.path.join("data","runs","run.csv"))
    ap.add_argument("--events", default=os.path.join("data","events","events.jsonl"))
    ap.add_argument("--out", default="plot_speed_vs_odom.png")
    ap.add_argument("--events-out-csv", default="events_timeline.csv")
    args = ap.parse_args()
    run = read_run_csv(args.run)
    events = read_events(args.events)
    evtable = build_event_table(events, run)
    plot_speed_vs_odom(run, evtable, args.out)
    save_events_csv(evtable, args.events_out_csv)
    print(f"[OK] Gráfico: {args.out}")
    print(f"[OK] Timeline eventos: {args.events_out_csv}")
    print(f"[INFO] Eventos considerados: {len(evtable)}")


if __name__ == "__main__":
    main()
