from __future__ import annotations

import json
import os
import time

from ingestion.rd_client import RDClient
from ingestion.lua_eventbus import LuaEventBus
from runtime.csv_logger import CsvLogger
from runtime.events_bus import normalize

# Archivos de salida
CSV_PATH = os.environ.get("RUN_CSV_PATH", os.path.join("data", "runs", "run.csv"))
EVT_PATH = os.environ.get("RUN_EVT_PATH", os.path.join("data", "events", "events.jsonl"))
HB_PATH = os.environ.get("RUN_HB_PATH", os.path.join("data", "events", ".collector_heartbeat"))

# Dónde leer los eventos que emite el LUA:
#  - Si existe la variable de entorno LUA_BUS_PATH → úsala
#  - En su defecto, usa la ruta por defecto del script LUA
LUA_BUS = os.environ.get(
    "LUA_BUS_PATH",
    os.path.join("data", "lua_eventbus.jsonl")
)


def run(poll_hz: float = 10.0, stop_time: float | None = None) -> None:
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(EVT_PATH), exist_ok=True)
    # Asegura que el fichero existe desde el arranque
    open(EVT_PATH, "a", encoding="utf-8").close()
    # Inicializa heartbeat para que otras utilidades (p.ej., drain) detecten que el colector está activo
    try:
        with open(HB_PATH, "w", encoding="utf-8") as hb:
            hb.write(str(time.time()))
    except Exception:
        pass

    rd = RDClient(poll_hz=poll_hz)
    csvlog = CsvLogger(CSV_PATH)
    bus = LuaEventBus(LUA_BUS, create_if_missing=True)
    # Primar cabecera con superset de campos (specials + controles + derivados)
    csvlog.init_with_fields(rd.schema())

    # Estado para odometría
    prev_t = None
    prev_v = None
    odom_m = 0.0

    # Señal del último evento escrito para de-dup
    last_sig = None  # (type, marker_or_station, time)

    # Mantener UN solo generador — el ritmo ya lo gobierna RDClient.stream()
    for row in rd.stream():
        # Auto-stop por tiempo si se indico
        if stop_time and time.time() >= stop_time:
            break
        now = time.time()
        row["t_wall"] = now
        # --- Odómetro (regla trapezoidal)
        v = float(row.get("v_ms") or 0.0)
        if prev_t is not None:
            dt = max(0.0, now - prev_t)
            v_prev = float(prev_v or v)
            odom_m += 0.5 * (v_prev + v) * dt
        row["odom_m"] = odom_m
        prev_t, prev_v = now, v
        csvlog.write_row(row)
        # Refresca heartbeat en cada tick (señal de vida del colector)
        try:
            with open(HB_PATH, "w", encoding="utf-8") as hb:
                hb.write(str(now))
        except Exception:
            pass

        # Drenar hasta 10 eventos por tick (para no quedarnos atrás)
        drained = 0
        while drained < 10:
            evt = bus.poll()
            if not evt:
                break
            # Enriquecer evento con telemetría del tick si faltan campos
            e = dict(evt)
            e["source"] = "collector"
            if e.get("lat") in (None, "") and row.get("lat") is not None:
                e["lat"] = float(row["lat"])  # type: ignore[arg-type]
            if e.get("lon") in (None, "") and row.get("lon") is not None:
                e["lon"] = float(row["lon"])  # type: ignore[arg-type]
            if e.get("time") is None:
                try:
                    h = float(row.get("time_ingame_h") or 0)
                    m = float(row.get("time_ingame_m") or 0)
                    s = float(row.get("time_ingame_s") or 0)
                    e["time"] = h + m/60.0 + s/3600.0
                except Exception:
                    pass
            if e.get("odom_m") is None:
                e["odom_m"] = odom_m

            # De-dup básico: mismo tipo+identificador+tiempo ⇒ no reescribir
            ident = (
                e.get("marker")
                or e.get("name")
                or e.get("station")
                or e.get("payload")
            )
            sig = (e.get("type"), ident, e.get("time"))
            if sig == last_sig:
                drained += 1
                continue
            last_sig = sig
            # Skip incomplete marker events lacking coordinates
            if e.get("type") == "marker_pass" and (
                e.get("lat") in (None, "") or e.get("lon") in (None, "")
            ):
                drained += 1
                continue
            nrm = normalize(e)
            with open(EVT_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(nrm, ensure_ascii=False) + "\n")
            drained += 1

if __name__ == "__main__":
    import argparse, time as _t
    ap = argparse.ArgumentParser()
    ap.add_argument("--hz", type=float, default=12.0, help="Frecuencia objetivo (Hz)")
    ap.add_argument("--duration", type=float, default=0.0, help="Segundos hasta auto-salida (0=infinito)")
    args = ap.parse_args()
    end_t = (_t.time() + args.duration) if args.duration > 0 else None
    run(args.hz, stop_time=end_t)

if __name__ == "__main__DISABLED_OLD":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--hz", type=float, default=12.0, help="Frecuencia objetivo")
    ap.add_argument("--duration", type=float, default=0.0, help="Segundos hasta auto-stop (0=sin límite)")
    args = ap.parse_args()
    import time as _t
    t0 = _t.time()
    try:
        run(args.hz)
    except KeyboardInterrupt:
        pass
if __name__ == "__main__DISABLED":
    run(12.0)  # 12 Hz objetivo ≈ 9–10 Hz efectivos
