from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from runtime.braking_era import EraCurve, compute_target_speed_kph_era
from runtime.braking_v0 import BrakingConfig, compute_target_speed_kph
from runtime.profiles import load_braking_profile, load_profile_extras

"""
Herramienta CLI para aplicar la frenada v0 / ERA a un run/dist CSV.
"""


def _read_csv_auto(path: Path) -> pd.DataFrame:
    # sep=None pide a pandas detectar delimitador (soporta ';' y ',')
    return pd.read_csv(path, sep=None, engine="python")


def _pick_series(df: pd.DataFrame, *cands: str) -> Optional[pd.Series]:
    for c in cands:
        if c in df.columns:
            return df[c]
    return None


def _speed_kph(df: pd.DataFrame) -> pd.Series:
    s = _pick_series(df, "v_kmh", "speed_kph", "kph", "speed_kmh")
    if s is None:
        raise KeyError(
            "No se encontró columna de velocidad (v_kmh/speed_kph/kph/speed_kmh)"
        )
    return s.astype(float)


def main() -> None:
    ap = argparse.ArgumentParser(description="Aplica regla de frenada v0 sobre un run")
    ap.add_argument("--log", required=True, type=Path)
    ap.add_argument("--dist", required=True, type=Path)
    ap.add_argument("--events", required=False, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument(
        "--profile", type=str, default=None, help="Ruta a profiles/<loco>.json"
    )
    ap.add_argument(
        "--era-curve",
        type=str,
        default=None,
        help="CSV con speed_kph,decel_service_mps2",
    )
    # Defaults a None para distinguir no especificado vs valor por defecto
    ap.add_argument("--A", type=float, default=None, help="Deceleración [m/s^2]")
    ap.add_argument(
        "--margin-kph", type=float, default=None, help="Margen bajo el límite [km/h]"
    )
    ap.add_argument(
        "--reaction", type=float, default=None, help="Tiempo de reacción [s]"
    )
    args = ap.parse_args()

    df_log = _read_csv_auto(args.log)
    df_dist = _read_csv_auto(args.dist)

    # Alinear datos: si ambos tienen t_wall, merge por tiempo; si no, por índice
    key = None
    for k in ("t_wall", "time_wall_s", "time", "t"):
        if k in df_log.columns and k in df_dist.columns:
            key = k
            break

    if key is not None:
        # Mantener del .dist solo columnas relevantes para evitar sufijos _x/_y
        keep_cols = [
            c for c in ("dist_next_limit_m", "next_limit_kph") if c in df_dist.columns
        ]
        right = df_dist[[key] + keep_cols].copy()
        left = df_log.copy()
        df = pd.merge_asof(
            left.sort_values(key),
            right.sort_values(key),
            on=key,
            direction="backward",
            allow_exact_matches=True,
        )
        df = df.set_index(df_log.index)  # restablecer índice del log
    else:
        # fallback: asumir alineación por índice/orden
        if len(df_log) != len(df_dist):
            # reindexar por la longitud mínima
            n = min(len(df_log), len(df_dist))
            df = pd.concat(
                [
                    df_log.iloc[:n].reset_index(drop=True),
                    df_dist.iloc[:n].reset_index(drop=True),
                ],
                axis=1,
            )
        else:
            df = pd.concat(
                [df_log.reset_index(drop=True), df_dist.reset_index(drop=True)], axis=1
            )

    v_kph = _speed_kph(df)
    dist = _pick_series(df, "dist_next_limit_m")
    next_lim = _pick_series(df, "next_limit_kph")

    if dist is None:
        raise KeyError(
            "No se encontró 'dist_next_limit_m' en el CSV de --dist. Genera antes con tools/dist_next_limit.py"
        )

    dist_arr = np.asarray(dist, dtype=float)
    lim_arr = np.asarray(next_lim, dtype=float) if next_lim is not None else None

    # Configuración desde perfil + overrides CLI
    cfg = BrakingConfig()
    if args.profile:
        cfg = load_braking_profile(args.profile, base=cfg)
        extras = load_profile_extras(args.profile)
    else:
        extras = {}
    if args.margin_kph is not None:
        cfg = replace(cfg, margin_kph=float(args.margin_kph))
    if args.A is not None:
        cfg = replace(cfg, max_service_decel=float(args.A))
    if args.reaction is not None:
        cfg = replace(cfg, reaction_time_s=float(args.reaction))

    # Curva ERA (precedencia: --era-curve > perfil > None)
    era_curve_path = args.era_curve or extras.get("era_curve_csv")
    curve = EraCurve.from_csv(era_curve_path) if era_curve_path else None

    if curve is not None:
        tgt: list[float] = []
        phase: list[str] = []
        v_arr = v_kph.to_numpy(dtype=float, copy=False)
        for i in range(len(v_arr)):
            v_now = float(v_arr[i])
            d_val = float(dist_arr[i]) if i < len(dist_arr) else np.nan
            lim_val = None
            if lim_arr is not None and i < len(lim_arr):
                lim_val = float(lim_arr[i])
                if np.isnan(lim_val):
                    lim_val = None
            d_opt = None if np.isnan(d_val) else d_val
            if lim_val is None:
                # Sin límite a la vista: mantener
                v_t, ph = v_now, "CRUISE"
            else:
                v_t, ph = compute_target_speed_kph_era(
                    v_now, lim_val, d_opt, curve=curve, cfg=cfg
                )
            tgt.append(v_t)
            phase.append(ph)
        v_max_kph = np.asarray(tgt, dtype=float)
    else:
        v_max_kph = compute_target_speed_kph(
            v_kph.to_numpy(dtype=float, copy=False),
            dist_arr,
            lim_arr,
            cfg,
        )

    needs_brake = (v_kph.to_numpy(dtype=float, copy=False) > (v_max_kph + 0.1)).astype(
        int
    )

    # Ensamblar salida: conservar columnas del log y añadir controles/dist/límite
    out_df = df_log.copy()
    if "dist_next_limit_m" in df.columns:
        out_df["dist_next_limit_m"] = df["dist_next_limit_m"]
    if "next_limit_kph" in df.columns:
        out_df["next_limit_kph"] = df["next_limit_kph"]
    out_df["ctrl_vmax_kph"] = v_max_kph
    out_df["ctrl_needs_brake"] = needs_brake
    try:
        if curve is not None:
            out_df["ctrl_phase"] = phase  # type: ignore[name-defined]
    except Exception:
        pass

    # Escribir con separador ';' para compatibilidad con tools/plot_run.py
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(args.out, index=False, sep=";")
    print(f"[ctrl] OK -> {args.out}")


if __name__ == "__main__":
    main()
