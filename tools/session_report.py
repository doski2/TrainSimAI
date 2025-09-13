from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def _load_csv(p: Path) -> pd.DataFrame:
    with p.open("r", encoding="utf-8", errors="ignore") as f:
        head = f.readline()
    sep = "," if head.count(",") >= head.count(";") else ";"
    df = pd.read_csv(p, sep=sep, engine="python")
    for c in [
        "t_wall",
        "odom_m",
        "speed_kph",
        "next_limit_kph",
        "dist_next_limit_m",
        "target_speed_kph",
        "throttle",
        "brake",
        "active_limit_kph",
    ]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "t_wall" in df.columns and not df["t_wall"].is_monotonic_increasing:
        df = df.sort_values("t_wall").reset_index(drop=True)
    return df


def _segment_events(df: pd.DataFrame) -> pd.DataFrame:
    need = ["next_limit_kph", "dist_next_limit_m"]
    if not all(c in df.columns for c in need):
        return pd.DataFrame(
            columns=[
                "event_id",
                "start_idx",
                "end_idx",
                "limit_kph",
                "d_start_m",
                "d_min_m",
                "arrived",
                "arrival_speed_kph",
                "ok_leq_limit_plus_0_5",
                "avg_margin_kph_last50m",
                "overspeed_cases",
                "overspeed_with_brake",
            ]
        )
    evs = []
    in_seg, start, cur_lim = False, None, None
    for i, (lim, dist) in enumerate(zip(df["next_limit_kph"], df["dist_next_limit_m"])):
        if pd.notna(lim) and pd.notna(dist):
            if not in_seg:
                in_seg, start, cur_lim = True, i, lim
            elif lim != cur_lim:
                evs.append((start, i - 1, cur_lim))
                start, cur_lim = i, lim
        else:
            if in_seg:
                evs.append((start, i - 1, cur_lim))
                in_seg, start, cur_lim = False, None, None
    if in_seg and start is not None:
        evs.append((start, len(df) - 1, cur_lim))
    rows = []
    for eid, (s, e, lim) in enumerate(evs, start=1):
        seg = df.iloc[s : e + 1]
        d_start = float(seg["dist_next_limit_m"].max())
        d_min = float(seg["dist_next_limit_m"].min())
        arrival = seg[seg["dist_next_limit_m"] <= 5]
        if len(arrival) > 0:
            j = arrival["dist_next_limit_m"].idxmin()
            if "speed_kph" in df.columns:
                val = df.loc[j, "speed_kph"]
                arrival_speed = float(np.asarray(val))
            else:
                arrival_speed = float("nan")
            arrived = True
        else:
            # fallback robusto: si min(dist) <= 8 m, consideramos que llegó
            j = seg["dist_next_limit_m"].idxmin()
            arrived = bool(seg["dist_next_limit_m"].min() <= 8.0)
            if arrived and "speed_kph" in df.columns:
                val = df.loc[j, "speed_kph"]
                arrival_speed = float(np.asarray(val))
            else:
                arrival_speed = float("nan")
        ok = bool(arrival_speed <= float(lim) + 0.5) if arrived else False
        last50 = seg[seg["dist_next_limit_m"] <= 50]
        avg_margin = float((last50["next_limit_kph"] - last50["speed_kph"]).mean()) if len(last50) else float("nan")
        if "speed_kph" in seg.columns and "brake" in seg.columns:
            m_over = seg["speed_kph"] > seg["next_limit_kph"] + 1.5
            overs = int(m_over.sum())
            overs_br = int((m_over & (seg["brake"] > 0.0)).sum())
        else:
            overs, overs_br = 0, 0
        rows.append(
            {
                "event_id": eid,
                "start_idx": s,
                "end_idx": e,
                "limit_kph": float(lim) if pd.notna(lim) else float("nan"),
                "d_start_m": d_start,
                "d_min_m": d_min,
                "arrived": arrived,
                "arrival_speed_kph": arrival_speed,
                "ok_leq_limit_plus_0_5": ok,
                "avg_margin_kph_last50m": avg_margin,
                "overspeed_cases": overs,
                "overspeed_with_brake": overs_br,
            }
        )
    return pd.DataFrame(rows)


def _compute_report(df: pd.DataFrame) -> dict:
    rep = {"rows": int(len(df)), "columns": list(df.columns)}
    if "t_wall" in df.columns and len(df) > 1:
        dt = df["t_wall"].diff().dropna()
        if len(dt):
            rep["hz_mean"] = float(1.0 / dt.mean())
            rep["dt_p95_s"] = float(np.percentile(dt, 95))
    for c in [
        "speed_kph",
        "next_limit_kph",
        "dist_next_limit_m",
        "target_speed_kph",
        "throttle",
        "brake",
        "active_limit_kph",
    ]:
        if c in df.columns:
            rep[f"nan_{c}"] = int(df[c].isna().sum())
    if all(c in df.columns for c in ["speed_kph", "next_limit_kph", "brake"]):
        mask_over = (df["next_limit_kph"].notna()) & (df["speed_kph"] > df["next_limit_kph"] + 1.5)
        rep["overspeed_cases"] = int(mask_over.sum())
        rep["overspeed_cases_with_brake"] = int((mask_over & (df["brake"] > 0.0)).sum())
    # monotonicidad distancia
    dist_viol = 0
    if "dist_next_limit_m" in df.columns and "next_limit_kph" in df.columns:
        prev_d, prev_lim = None, None
        for d, lim in zip(df["dist_next_limit_m"], df["next_limit_kph"]):
            if pd.isna(d):
                prev_d = None
                prev_lim = lim
                continue
            if lim != prev_lim:
                prev_d = None
                prev_lim = lim
            if prev_d is not None and (d - prev_d) > 2.0:
                dist_viol += 1
            prev_d = d
        rep["dist_increases_gt2m"] = int(dist_viol)
    return rep


def _write_txt(path: Path, rep: dict, ev_df: pd.DataFrame | None):
    with path.open("w", encoding="utf-8") as f:
        for k, v in rep.items():
            f.write(f"{k}: {v}\n")
        if ev_df is not None and not ev_df.empty:
            arr = int(ev_df["arrived"].sum())
            ok = int(ev_df["ok_leq_limit_plus_0_5"].sum())
            rate = ok / max(1, arr)
            f.write("--- events ---\n")
            f.write(f"events_found: {len(ev_df)}\n")
            f.write(f"arrivals_checked: {arr}\n")
            f.write(f"arrivals_ok_<=+0.5kph: {ok}\n")
            f.write(f"arrivals_ok_rate: {rate:.3f}\n")


def _plots(df: pd.DataFrame, stem: Path):
    if "speed_kph" in df.columns and "target_speed_kph" in df.columns:
        plt.figure()
        plt.plot(df["speed_kph"], label="speed_kph")
        plt.plot(df["target_speed_kph"], label="target_speed_kph")
        plt.title("Velocidad vs objetivo")
        plt.xlabel("muestra")
        plt.ylabel("km/h")
        plt.legend()
        plt.savefig(stem.with_suffix("").as_posix() + "_speed_target.png", dpi=130)
        plt.close()
    if "dist_next_limit_m" in df.columns:
        plt.figure()
        plt.plot(df["dist_next_limit_m"])
        plt.title("Distancia al próximo límite")
        plt.xlabel("muestra")
        plt.ylabel("m")
        plt.savefig(stem.with_suffix("").as_posix() + "_dist.png", dpi=130)
        plt.close()
    if ("throttle" in df.columns) or ("brake" in df.columns):
        plt.figure()
        if "throttle" in df.columns:
            plt.plot(df["throttle"], label="throttle")
        if "brake" in df.columns:
            plt.plot(df["brake"], label="brake")
        plt.title("Actuadores")
        plt.xlabel("muestra")
        plt.ylabel("0..1")
        plt.legend()
        plt.savefig(stem.with_suffix("").as_posix() + "_actuators.png", dpi=130)
        plt.close()


def main():
    ap = argparse.ArgumentParser(description="Informe de sesión ctrl_live")
    ap.add_argument("--in", dest="inp", required=True, help="Ruta al ctrl_live_*.csv")
    ap.add_argument("--no-plots", action="store_true", help="No generar PNGs")
    args = ap.parse_args()
    in_path = Path(args.inp)
    df = _load_csv(in_path)
    rep = _compute_report(df)
    ev_df = _segment_events(df)
    # guardar
    rep_txt = in_path.with_name(in_path.stem + "_report.txt")
    _write_txt(rep_txt, rep, ev_df)
    if ev_df is not None and not ev_df.empty:
        ev_csv = in_path.with_name(in_path.stem + "_events.csv")
        ev_df.to_csv(ev_csv, index=False)
    if not args.no_plots:
        _plots(df, in_path)
    print(f"[session_report] txt={rep_txt}")
    if ev_df is not None and not ev_df.empty:
        print(f"[session_report] events_csv={in_path.with_name(in_path.stem + '_events.csv')}")


if __name__ == "__main__":
    main()
