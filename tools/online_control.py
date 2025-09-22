from __future__ import annotations

import argparse
import csv
import json
import os
import time
from dataclasses import replace
from pathlib import Path
from typing import Optional

import numpy as np

from runtime.braking_era import EraCurve, compute_target_speed_kph_era
from runtime.braking_v0 import BrakingConfig, compute_target_speed_kph
from runtime.guards import RateLimiter, clamp01, overspeed_guard
from runtime.profiles import load_braking_profile, load_profile_extras

"""
Control online (MVP) basado en run.csv y eventos getdata_next_limit.

Lee periódicamente la última fila de `--run` y eventos de `--events` (JSONL),
calcula velocidad objetivo con frenada v0 o ERA y genera un CSV de control
con throttle/brake en `--out`.

Uso:
  python -m tools.online_control \
    --run data/run.csv \
    --events data/events.jsonl \
    --out data/run.ctrl_online.csv \
    --hz 5 \
    --profile profiles/BR146.json [--era-curve profiles/BR146_era_curve.csv]
"""


def tail_csv_last_row(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        # Auto-separador + fallback seguro.
        with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
            # Leer cabecera (primera línea)
            try:
                header_line = f.readline()
            except Exception:
                return None
            if not header_line:
                return None
            # Tomar una muestra para detectar separador
            try:
                sample = header_line + f.read(4096)
            except Exception:
                sample = header_line
            delim = ";" if sample.count(";") >= sample.count(",") else ","
            header = [h.strip() for h in header_line.rstrip("\n\r").split(delim)]

            # Leer un trozo final razonable para localizar la última línea completa
            f.seek(0, os.SEEK_END)
            size = f.tell()
            tail_start = max(0, size - 65536)
            f.seek(tail_start)
            tail = f.read()
            if not tail:
                return None
            lines = tail.splitlines()
            # Si empezamos en mitad de línea, descartamos la primera línea parcial
            if tail_start > 0 and lines:
                lines = lines[1:]
            if not lines:
                return None

            # Buscar la última línea no vacía
            last_line = None
            for cand in reversed(lines):
                if cand.strip():
                    last_line = cand
                    break
            if last_line is None:
                return None

            last_vals = last_line.split(delim)
            # Si el número de columnas no coincide, intentar la línea anterior
            if len(last_vals) != len(header):
                found = False
                for cand in reversed(lines[:-1]):
                    if not cand.strip():
                        continue
                    vals = cand.split(delim)
                    if len(vals) == len(header):
                        last_vals = vals
                        found = True
                        break
                if not found:
                    # Fallback seguro: usar csv.DictReader para manejar comillas/escapes
                    f.seek(0)
                    rd = csv.DictReader(f, delimiter=delim)
                    last_row = None
                    for row in rd:
                        last_row = row
                    return last_row

            # Mapear header -> valores (ignorando extras)
            row = {}
            for i, key in enumerate(header):
                row[key] = last_vals[i] if i < len(last_vals) else ""
            return row
    except Exception:
        return None


class NonBlockingEventStream:
    def __init__(self, path: Path, *, from_end: bool = False) -> None:
        self.path = path
        self._pos = 0
        try:
            if from_end and path.exists():
                self._pos = path.stat().st_size
        except Exception:
            self._pos = 0

    def __next__(self) -> dict:
        if not self.path.exists():
            raise StopIteration
        with self.path.open("r", encoding="utf-8", errors="ignore") as f:
            f.seek(self._pos)
            line = f.readline()
            if not line:
                raise StopIteration
            self._pos = f.tell()
        try:
            return json.loads(line)
        except Exception:
            raise StopIteration


class SplitPID:
    """Controlador simple: error en km/h -> throttle/brake [0..1]."""

    def __init__(self, kp_th: float = 0.03, kp_br: float = 0.04) -> None:
        self.kp_th = float(kp_th)
        self.kp_br = float(kp_br)

    def update(
        self, v_target_kph: float, v_now_kph: float, dt: float
    ) -> tuple[float, float]:
        e = float(v_target_kph) - float(v_now_kph)
        if e >= 0:
            th = clamp01(self.kp_th * e)
            br = 0.0
        else:
            th = 0.0
            br = clamp01(self.kp_br * (-e))
        return th, br


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Control online a partir de run.csv y eventos"
    )
    ap.add_argument("--run", type=Path, default=Path("data/run.csv"))
    ap.add_argument("--events", type=Path, default=Path("data/events.jsonl"))
    ap.add_argument("--out", type=Path, default=Path("data/run.ctrl_online.csv"))
    ap.add_argument("--hz", type=float, default=5.0)
    ap.add_argument("--profile", type=str, default=None)
    ap.add_argument("--era-curve", type=str, default=None)
    ap.add_argument(
        "--start-events-from-end",
        action="store_true",
        help="Empezar a leer events.jsonl desde el final",
    )
    ap.add_argument(
        "--duration",
        type=float,
        default=0.0,
        help="Segundos hasta auto-salida (0 = infinito)",
    )
    # Overrides CLI (opcionales)
    ap.add_argument("--A", type=float, default=None)
    ap.add_argument("--margin-kph", type=float, default=None)
    ap.add_argument("--reaction", type=float, default=None)
    args = ap.parse_args()

    run_path: Path = args.run
    events_path: Path = args.events
    out_path: Path = args.out

    # Configuración de frenada
    cfg = BrakingConfig()
    extras = {}
    if args.profile:
        cfg = load_braking_profile(args.profile, base=cfg)
        extras = load_profile_extras(args.profile)
    if args.margin_kph is not None:
        cfg = replace(cfg, margin_kph=float(args.margin_kph))
    if args.A is not None:
        cfg = replace(cfg, max_service_decel=float(args.A))
    if args.reaction is not None:
        cfg = replace(cfg, reaction_time_s=float(args.reaction))

    era_curve_path = args.era_curve or extras.get("era_curve_csv")
    curve = EraCurve.from_csv(era_curve_path) if era_curve_path else None

    # Estado de eventos y rate limiters
    ev_stream = NonBlockingEventStream(
        events_path, from_end=bool(args.start_events_from_end)
    )
    rl_th = RateLimiter(max_delta_per_s=0.8)
    rl_br = RateLimiter(max_delta_per_s=1.2)
    # pid eliminado: no se utiliza

    # Estado de próxima señal de límite
    next_limit_kph: Optional[float] = None
    anchor_dist_m: Optional[float] = None
    anchor_odom_m: Optional[float] = None
    # last_phase eliminado: no se utiliza
    last_limit_kph: Optional[float] = None
    last_dist_m: Optional[float] = None
    last_t_wall_written: Optional[float] = None

    # CSV salida
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not out_path.exists():
        with out_path.open("w", newline="", encoding="utf-8") as fo:
            wr = csv.writer(fo)
            wr.writerow(
                [
                    "t_wall",
                    "odom_m",
                    "speed_kph",
                    "next_limit_kph",
                    "dist_next_limit_m",
                    "target_speed_kph",
                    "phase",
                    "throttle",
                    "brake",
                ]
            )

    period = 1.0 / max(0.5, float(args.hz))
    t0 = time.perf_counter()
    t_next = t0
    # last_tick eliminado: no se utiliza

    while True:
        if args.duration and (time.perf_counter() - t0) >= float(args.duration):
            break
        # 1) absorber eventos disponibles (sin bloquear)
        for _ in range(100):
            try:
                ev = next(ev_stream)
            except StopIteration:
                break
            except Exception:
                break
            if isinstance(ev, dict) and ev.get("type") == "getdata_next_limit":
                kph = ev.get("kph") or ev.get("speed_kph") or ev.get("limit_kph")
                dist = ev.get("dist_m") or ev.get("dist")
                if kph is not None and dist is not None:
                    next_limit_kph = float(kph)
                    anchor_dist_m = max(0.0, float(dist))
                    # tomaremos anchor_odom_m en el siguiente sampleo de run.csv
                    anchor_odom_m = None

        # 2) muestrear última fila de run.csv
        row = tail_csv_last_row(run_path)
        if row is None:
            time.sleep(0.05)
            continue

        try:
            t_wall = float(row.get("t_wall", "nan"))
            odom_m = float(row.get("odom_m", "nan"))
            # compat: speed_kph o v_kmh
            v = row.get("speed_kph") or row.get("v_kmh") or row.get("SpeedometerKPH")
            speed_kph = float(v if v is not None else "nan")
        except Exception:
            time.sleep(0.05)
            continue

        # Evitar duplicados: si no hay nueva muestra, no escribimos
        if last_t_wall_written is not None and abs(t_wall - last_t_wall_written) < 1e-6:
            # espera al siguiente tick, sin escribir
            t_next += period
            delay = t_next - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            else:
                t_next = time.perf_counter()
            continue

        # 3) calcular dist_next_limit_m por odómetro
        if next_limit_kph is None or anchor_dist_m is None:
            dist_next_limit_m = None
        else:
            if anchor_odom_m is None:
                anchor_odom_m = odom_m
            traveled = max(0.0, odom_m - anchor_odom_m)
            dist_raw = max(0.0, anchor_dist_m - traveled)
            # clamp monótono: si el límite no cambió, no permitimos subir distancia
            if (
                last_limit_kph is not None
                and next_limit_kph == last_limit_kph
                and last_dist_m is not None
                and dist_raw > last_dist_m
            ):
                dist_next_limit_m = last_dist_m
            else:
                dist_next_limit_m = dist_raw
            last_dist_m = dist_next_limit_m
            last_limit_kph = next_limit_kph

        # 4) objetivo y PID
        if curve and next_limit_kph is not None:
            v_tgt, phase = compute_target_speed_kph_era(
                speed_kph, next_limit_kph, dist_next_limit_m, curve=curve, cfg=cfg
            )
        else:
            # compute_target_speed_kph (vectorizado) -> usar tamaño 1
            v_tgt = float(
                compute_target_speed_kph(
                    np.asarray([speed_kph]),
                    np.asarray(
                        [dist_next_limit_m if dist_next_limit_m is not None else np.nan]
                    ),
                    (
                        np.asarray([next_limit_kph])
                        if next_limit_kph is not None
                        else None
                    ),
                    cfg,
                )[0]
            )
            phase = (
                "BRAKE"
                if v_tgt < speed_kph - cfg.coast_band_kph
                else (
                    "COAST"
                    if abs(v_tgt - speed_kph) <= cfg.coast_band_kph
                    else "CRUISE"
                )
            )

        # Failsafe: si algo devolviera NaN, usar velocidad actual
        if not (v_tgt == v_tgt):  # NaN check
            v_tgt = float(speed_kph)
            phase = "CRUISE"

        th, br = SplitPID().update(v_tgt, speed_kph, dt=period)
        # aplicar rate limiters
        th = rl_th.step(th, period)
        br = rl_br.step(br, period)
        # overspeed guard (mínimo de freno)
        br = max(br, overspeed_guard(speed_kph, next_limit_kph))
        if br > 0:
            th = 0.0

        # 5) registrar
        with out_path.open("a", newline="", encoding="utf-8") as fo:
            wr = csv.writer(fo)
            wr.writerow(
                [
                    t_wall,
                    odom_m,
                    speed_kph,
                    next_limit_kph or "",
                    dist_next_limit_m or "",
                    v_tgt,
                    phase,
                    round(th, 3),
                    round(br, 3),
                ]
            )
        last_t_wall_written = t_wall

        # 6) temporización de bucle
        t_next += period
        delay = t_next - time.perf_counter()
        if delay > 0:
            time.sleep(delay)
        else:
            t_next = time.perf_counter()


if __name__ == "__main__":
    main()
