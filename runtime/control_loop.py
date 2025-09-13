from __future__ import annotations

import argparse
from dataclasses import replace
import time
import csv
import json
from pathlib import Path
from typing import Optional

import numpy as np

from runtime.braking_v0 import BrakingConfig, compute_target_speed_kph
from runtime.braking_era import EraCurve, compute_target_speed_kph_era
from runtime.profiles import load_braking_profile, load_profile_extras
from runtime.guards import RateLimiter, JerkBrakeLimiter, overspeed_guard
from runtime.csv_logger import CSVLogger
from storage.run_store_sqlite import RunStore
import math

# Reutilizamos utilidades de tools.online_control
from tools.online_control import NonBlockingEventStream, SplitPID


def tail_csv_last_row(path: Path) -> dict | None:
    """Lee la última fila completa del CSV usando la cabecera real y detectando el delimitador.
    Estrategia: detecta delimitador en la PRIMERA línea; luego lee desde el final con ventanas
    crecientes (64 KiB → 2 MiB) hasta encontrar una fila completa que case con la cabecera.
    Soporta ',', ';', '\t', '|'.
    """
    if not path.exists():
        return None

    # 1) Leer cabecera REAL (primera línea) y detectar delimitador.
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            header_line = f.readline()
    except Exception:
        return None
    if not header_line:
        return None

    def _pick_delim(line: str) -> str:
        cands = [",", ";", "\t", "|"]
        counts = [(d, line.count(d)) for d in cands]
        delim = max(counts, key=lambda t: t[1])[0]
        return delim if line.count(delim) > 0 else ","

    delim = _pick_delim(header_line)
    try:
        header = next(csv.reader([header_line], delimiter=delim))
    except Exception:
        return None
    if not header:
        return None
    ncols = len(header)

    # 2) Leer desde el final con ventanas crecientes hasta encontrar una fila válida.
    max_window = 2 * 1024 * 1024  # 2 MiB
    window = 64 * 1024  # 64 KiB inicial
    filesize = path.stat().st_size
    with path.open("rb") as fb:
        while True:
            try:
                fb.seek(-min(window, filesize), 2)
            except OSError:
                fb.seek(0)
            chunk = fb.read().decode("utf-8", errors="ignore")
            lines = [ln for ln in chunk.splitlines() if ln.strip()]
            for cand in reversed(lines):
                try:
                    fields = next(csv.reader([cand], delimiter=delim))
                except Exception:
                    continue
                # saltar cabeceras/repeticiones
                if [c.strip().lower() for c in fields] == [h.strip().lower() for h in header]:
                    continue
                if len(fields) == ncols:
                    return {k: v for k, v in zip(header, fields)}
            if window >= max_window or window >= filesize:
                break
            window = min(window * 2, max_window)
    return None


def _to_float_loose(val: object) -> float:
    """Convierte strings a float tolerando formato con miles '.' y decimales ','.
    '', None o 'nan' -> NaN."""
    if val is None:
        return float("nan")
    s = str(val).strip().strip('"').strip("'")
    if s == "" or s.lower() == "nan":
        return float("nan")
    # si tiene coma, asumimos coma decimal; quitamos puntos como miles
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        # si hay >1 puntos, probablemente son miles -> quítalos
        if s.count(".") > 1:
            s = s.replace(".", "")
    try:
        return float(s)
    except Exception:
        return float("nan")


def main() -> None:
    ap = argparse.ArgumentParser(description="Control online a partir de run.csv y eventos")
    ap.add_argument("--run", type=Path, default=Path("data/runs/run.csv"))
    ap.add_argument("--events", type=Path, default=Path("data/events.jsonl"))
    ap.add_argument("--emit-active-limit", action="store_true",
                    help="Incluye columna active_limit_kph en la salida CSV")
    ap.add_argument("--bus", default="data/lua_eventbus.jsonl", help="Event bus JSONL (fallback si events.jsonl no avanza)")
    ap.add_argument("--out", type=Path, default=Path("data/run.ctrl_online.csv"))
    ap.add_argument("--hz", type=float, default=5.0)
    ap.add_argument("--db", default="data/run.db")
    ap.add_argument("--source", choices=["sqlite", "csv"], default="sqlite")
    ap.add_argument("--no-csv-fallback", action="store_true", help="Desactiva fallback a CSV si SQLite está vacío")
    ap.add_argument(
        "--derive-speed-if-missing",
        action="store_true",
        default=True,
        help="Si falta speed_kph, derivarla de odom_m (por defecto: activado)",
    )
    ap.add_argument(
        "--no-derive-speed", action="store_true", help="Desactiva la derivación automática de speed_kph si falta"
    )
    ap.add_argument("--profile", type=str, default=None)
    ap.add_argument("--era-curve", type=str, default=None)
    ap.add_argument("--start-events-from-end", action="store_true", help="Empezar a leer events.jsonl desde el final")
    ap.add_argument("--duration", type=float, default=0.0, help="Segundos hasta auto-salida (0 = infinito)")
    # Overrides CLI (opcionales)
    ap.add_argument("--A", type=float, default=None)
    ap.add_argument("--margin-kph", type=float, default=None)
    ap.add_argument("--reaction", type=float, default=None)
    args = ap.parse_args()

    run_path: Path = args.run
    events_path: Path = args.events
    out_path: Path = args.out
    bus_path: Path = Path(args.bus)

    # Configuración de frenada
    cfg = BrakingConfig()
    extras = {}
    if args.profile:
        cfg = load_braking_profile(args.profile, base=cfg)
        extras = load_profile_extras(args.profile)
        # si el perfil tiene bloque 'braking', mapear claves conocidas a BrakingConfig
        if isinstance(extras, dict) and "braking" in extras and isinstance(extras["braking"], dict):
            b = extras["braking"]
            # keys posibles que podrían venir del bloque 'braking'
            mapping_keys = {
                "a_service_mps2": "max_service_decel",
                "max_service_decel": "max_service_decel",
                "t_react_s": "reaction_time_s",
                "reaction_time_s": "reaction_time_s",
                "margin_m": None,  # distancia, no es directamente mapeable en BrakingConfig
                "v_margin_kph": "margin_kph",
                "margin_kph": "margin_kph",
            }
            vals = {}
            for src, dst in mapping_keys.items():
                if src in b and dst is not None:
                    try:
                        vals[dst] = float(b[src])
                    except Exception:
                        pass
            if vals:
                cfg = replace(cfg, **vals)
    if args.margin_kph is not None:
        cfg = replace(cfg, margin_kph=float(args.margin_kph))
    if args.A is not None:
        cfg = replace(cfg, max_service_decel=float(args.A))
    if args.reaction is not None:
        cfg = replace(cfg, reaction_time_s=float(args.reaction))

    era_curve_path = args.era_curve or extras.get("era_curve_csv")
    curve = EraCurve.from_csv(era_curve_path) if era_curve_path else None

    # Estado de eventos y rate limiters
    ev_stream = NonBlockingEventStream(events_path, from_end=bool(args.start_events_from_end))
    rl_th = RateLimiter(max_delta_per_s=0.8)
    jerk_br = JerkBrakeLimiter(max_rate_per_s=1.2, max_jerk_per_s2=3.0)

    # Estado de próxima señal de límite
    next_limit_kph: Optional[float] = None
    anchor_dist_m: Optional[float] = None
    anchor_odom_m: Optional[float] = None
    last_limit_kph: Optional[float] = None
    last_dist_m: Optional[float] = None
    # última fase observada (CRUISE/COAST/BRAKE) — necesario para detectar entrada en frenada
    last_phase: Optional[str] = None
    # EMA para suavizar speed solo a efectos de objetivo
    speed_ema: Optional[float] = None
    # Límite en vigor (tras cruzar el hito). Se usa para guard/vel objetivo si no hay "próximo límite"
    active_limit_kph: Optional[float] = None
    last_t_wall_written: Optional[float] = None

    # CSV salida con logger (coma, append seguro)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    writer = CSVLogger(
        out_path,
        delimiter=",",
        base_order=[
            "t_wall",
            "odom_m",
            "speed_kph",
            "next_limit_kph",
            "dist_next_limit_m",
            "target_speed_kph",
            "phase",
            "throttle",
            "brake",
        ],
    )

    # Fuente de datos opcional: SQLite
    store = RunStore(args.db) if args.source == "sqlite" else None
    last_rowid = 0
    use_csv = args.source == "csv"
    # decidir si derivamos speed_kph cuando falta (flag y complemento)
    derive_speed = bool(args.derive_speed_if_missing)
    if getattr(args, "no_derive_speed", False):
        derive_speed = False

    # Informar al inicio sobre las opciones relevantes (útil para debugging)
    print(
        f"[control] source={args.source} db={args.db} derive_speed_if_missing={derive_speed} no_csv_fallback={args.no_csv_fallback}"
    )
    # memoria para derivar velocidad si falta
    prev_t_wall: float | None = None
    prev_odom_m: float | None = None

    period = 1.0 / max(0.5, float(args.hz))
    t0 = time.perf_counter()
    t_next = t0

    # Puntero para tail del bus (empezar desde el final si se pidió --start-events-from-end)
    bus_pos = 0
    try:
        bus_pos = bus_path.stat().st_size if args.start_events_from_end else 0
    except Exception:
        bus_pos = 0

    def _drain_bus_events(path: Path, pos: int):
        if not path.exists():
            return [], pos
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as f:
                f.seek(pos)
                chunk = f.read()
                pos = f.tell()
        except Exception:
            return [], pos
        evs = []
        for ln in chunk.splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                ev = json.loads(ln)
            except Exception:
                continue
            evs.append(ev)
        return evs, pos

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
                    anchor_odom_m = None

        # 2) muestrear última fila de run.csv (fuente configurable)
        if store is not None and not use_csv:
            latest = store.latest_since(last_rowid)
            if latest is None:
                # activa CSV inmediatamente si SQLite no tiene nada
                if not args.no_csv_fallback:
                    use_csv = True
                time.sleep(0.05)
                continue
            else:
                last_rowid, row = latest
        if use_csv:
            row = tail_csv_last_row(run_path)
            if row is None:
                time.sleep(0.05)
                continue

        # Conversión robusta; speed puede faltar
        if row is None:
            time.sleep(0.05)
            continue
        t_wall = _to_float_loose(row.get("t_wall", ""))
        odom_m = _to_float_loose(row.get("odom_m", ""))
        # compat: speed_kph o v_kmh
        v = row.get("speed_kph") or row.get("v_kmh") or row.get("SpeedometerKPH")
        speed_kph = _to_float_loose(v)
        # EMA con tau ~0.4 s => alpha ≈ dt / (tau + dt)
        dt_real = period  # por defecto, pero si t_wall es confiable, usar diferencia real
        if last_t_wall_written is not None and t_wall > last_t_wall_written:
            dt_real = t_wall - last_t_wall_written
        tau = 0.4
        alpha = dt_real / (tau + dt_real) if dt_real > 0 else 0.2
        speed_ema = speed_kph if speed_ema is None else (1 - alpha) * speed_ema + alpha * speed_kph
        speed_for_target = speed_ema
        if any(math.isnan(x) for x in (t_wall, odom_m)):
            time.sleep(0.05)
            continue
        # Derivar velocidad si falta y está habilitado
        if (math.isnan(speed_kph) or speed_kph is None) and derive_speed:
            if prev_t_wall is not None and prev_odom_m is not None:
                dt = max(1e-3, t_wall - prev_t_wall)
                dv = odom_m - prev_odom_m
                speed_kph = max(0.0, (dv / dt) * 3.6)
            else:
                # aún no podemos derivar (primera muestra): guardamos y esperamos la siguiente
                prev_t_wall, prev_odom_m = t_wall, odom_m
                # mantener la temporización del bucle
                time.sleep(0.05)
                continue
        prev_t_wall, prev_odom_m = t_wall, odom_m

        # --- LEER EVENTOS DEL BUS (getdata_next_limit) ---
        evs, bus_pos = _drain_bus_events(bus_path, bus_pos)
        for ev in evs:
            et = ev.get("type")
            if et == "getdata_next_limit":
                kph = ev.get("kph") or ev.get("speed_kph") or ev.get("limit_kph")
                dist = ev.get("dist_m") or ev.get("dist")
                if kph is not None and dist is not None:
                    next_limit_kph = float(kph)
                    anchor_dist_m = float(dist)
                    anchor_odom_m = odom_m
                    try:
                        print(f"[control] next_limit={next_limit_kph} kph  dist≈{anchor_dist_m} m")
                    except Exception:
                        pass
        if math.isnan(speed_kph):
            time.sleep(0.05)
            continue

        # Evitar duplicados: si no hay nueva muestra, no escribimos
        if last_t_wall_written is not None and abs(t_wall - last_t_wall_written) < 1e-6:
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

        # 3.1) Si ya estamos "en" el hito (distances cercanas a 0), promover el límite a 'activo'
        if dist_next_limit_m is not None and dist_next_limit_m <= 2.0:
            try:
                active_limit_kph = float(next_limit_kph) if next_limit_kph is not None else active_limit_kph
            except Exception:
                pass
            # limpiar el próximo límite y su anclaje
            next_limit_kph = None
            anchor_dist_m = None
            anchor_odom_m = None
            dist_next_limit_m = None
            last_dist_m = None
            last_limit_kph = None

        # 4) objetivo y PID
        if curve and next_limit_kph is not None:
            v_tgt, phase = compute_target_speed_kph_era(
                speed_for_target, next_limit_kph, dist_next_limit_m, curve=curve, cfg=cfg
            )
        elif next_limit_kph is not None and dist_next_limit_m is not None:
            # sin curva ERA, usar v0 vectorizado sobre el próximo límite
            v_tgt = float(
                compute_target_speed_kph(
                    np.asarray([speed_kph]),
                    np.asarray([dist_next_limit_m if dist_next_limit_m is not None else np.nan]),
                    np.asarray([next_limit_kph]) if next_limit_kph is not None else None,
                    cfg,
                )[0]
            )
            phase = (
                "BRAKE"
                if v_tgt < speed_kph - cfg.coast_band_kph
                else ("COAST" if abs(v_tgt - speed_kph) <= cfg.coast_band_kph else "CRUISE")
            )
        elif active_limit_kph is not None:
            # No hay próximo límite; mantener por debajo del límite activo con margen
            try:
                v_margin = float(getattr(cfg, "margin_kph", 2.0))
            except Exception:
                v_margin = 2.0
            v_tgt = min(speed_kph, max(0.0, active_limit_kph - v_margin))
            phase = "COAST" if v_tgt < speed_kph - 0.1 else "CRUISE"
        else:
            v_tgt = speed_kph
            phase = "CRUISE"

        # Failsafe: si algo devolviera NaN, usar velocidad actual
        if not (v_tgt == v_tgt):  # NaN check
            v_tgt = float(speed_kph)
            phase = "CRUISE"

        th, br = SplitPID().update(v_tgt, speed_kph, dt=period)
        # aplicar rate limiters
        th = rl_th.step(th, period)
        # overspeed guard (mínimo de freno) — aplicamos al próximo si existe, si no al activo
        og = overspeed_guard(speed_kph, next_limit_kph if next_limit_kph is not None else active_limit_kph)

        # 4.1) Guard FÍSICO por distancia (a_req > a_service -> pisar más freno)
        try:
            a_service = float(getattr(cfg, "a_service_mps2", 0.6))
            if dist_next_limit_m is not None and next_limit_kph is not None:
                v = max(0.0, speed_kph) / 3.6
                vlim = max(0.0, next_limit_kph) / 3.6
                d = max(1.0, float(dist_next_limit_m))  # evita div/0
                a_req = max(0.0, (v*v - vlim*vlim) / (2.0 * d))
                if a_req > 0.70 * a_service:
                    phase = "BRAKE"
                    # mapear (a_req / a_service) a mando de freno (0..1), con ganancia suave
                    br = max(br, min(1.0, 0.4 + 0.9 * (a_req / max(0.1, a_service))))
        except Exception:
            pass
        # decidir si hemos entrado en fase de frenada recientemente
        just_entered_brake = (phase == "BRAKE" and last_phase != "BRAKE") or og > 0.0
        if just_entered_brake:
            rl_th.reset(0.0)
            # reset suave del limitador con reenganche
            jerk_br.reset(jerk_br.step(0.0, 1e-3))
            th = 0.0
        br = jerk_br.step(br, period)
        # aplicar overspeed como piso
        br = max(br, og)
        if br > 0:
            th = 0.0
        last_phase = phase

        # 5) registrar usando CSVLogger
        row_out = {
            "t_wall": float(t_wall),
            "odom_m": float(odom_m),
            "speed_kph": float(speed_kph),
            "next_limit_kph": "" if next_limit_kph is None else float(next_limit_kph),
            "dist_next_limit_m": "" if dist_next_limit_m is None else float(dist_next_limit_m),
            "target_speed_kph": float(v_tgt),
            "phase": phase,
            "throttle": float(round(th, 3)),
            "brake": float(round(br, 3)),
        }
        if getattr(args, "emit_active_limit", False):
            row_out["active_limit_kph"] = active_limit_kph if active_limit_kph is not None else ""
        writer.write_row(row_out)
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
