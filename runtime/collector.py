from __future__ import annotations

import functools
import json
import os
import time

from ingestion.rd_client import RDClient
import math
from ingestion.lua_eventbus import LuaEventBus
from runtime.csv_logger import CSVLogger
from math import radians, sin, cos, asin

try:
    from storage.run_store_sqlite import RunStore
except Exception:
    RunStore = None  # type: ignore
from runtime.events_bus import normalize


# Small, reusable retry decorator for transient failures.
# Usage: decorate small IO functions that may fail transiently. Keeps defaults
# conservative; tests override delays to be fast.
def retry_on_exception(max_attempts: int = 3, base_delay: float = 0.1, max_delay: float = 2.0, exceptions: tuple = (Exception,)):
    """Return a decorator that retries the wrapped callable on exception.

    - max_attempts: total attempts (including the first)
    - base_delay: initial backoff in seconds
    - max_delay: maximum backoff cap
    - exceptions: tuple of exception classes that trigger a retry
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except exceptions:
                    attempt += 1
                    if attempt >= max_attempts:
                        # re-raise the last exception
                        raise
                    # exponential backoff (2^(attempt-1))
                    delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
                    try:
                        time.sleep(delay)
                    except Exception:
                        # if sleep is interrupted, continue to retry loop
                        pass

        return wrapper

    return decorator

# Archivos de salida
CSV_PATH = os.environ.get("RUN_CSV_PATH", os.path.join("data", "runs", "run.csv"))
EVT_PATH = os.environ.get("RUN_EVT_PATH", os.path.join("data", "events", "events.jsonl"))
HB_PATH = os.environ.get("RUN_HB_PATH", os.path.join("data", "events", ".collector_heartbeat"))

# Dónde leer los eventos que emite el LUA:
#  - Si existe la variable de entorno LUA_BUS_PATH → úsala
#  - En su defecto, usa la ruta por defecto del script LUA
LUA_BUS = os.environ.get("LUA_BUS_PATH", os.path.join("data", "lua_eventbus.jsonl"))


def run(
    hz: float = 10.0,
    stop_time: float | None = None,
    bus_from_start: bool = False,
    sqlite_db: str = "data/run.db",
) -> None:
    # Inicializa heartbeat para que otras utilidades (p.ej., drain) detecten que el colector está activo
    try:
        with open(HB_PATH, "w", encoding="utf-8") as hb:
            hb.write(str(time.time()))
    except Exception:
        pass

    rd = RDClient(poll_hz=hz)
    csvlog = CSVLogger(
        CSV_PATH,
        base_order=[
            "t_wall",
            "time_ingame_h",
            "time_ingame_m",
            "time_ingame_s",
            "lat",
            "lon",
            "heading",
            "gradient",
            "v_ms",
            "v_kmh",
            "odom_m",
        ],
    )
    # Opcional: store en SQLite si está disponible y se pasó sqlite_db
    store = None
    if RunStore is not None and sqlite_db:
        try:
            store = RunStore(sqlite_db)
        except Exception as e:
            print(f"[collector] SQLite deshabilitado: {e}")
    # si bus_from_start=True => NO tail; leer desde el principio
    bus = LuaEventBus(LUA_BUS, create_if_missing=True, from_end=(not bus_from_start))
    # Primar cabecera con superset de campos (specials + controles + derivados)
    csvlog.init_with_fields(rd.schema())

    # --- estado para derivar odómetro/velocidad ---
    prev_t: float | None = None
    prev_lat: float | None = None
    prev_lon: float | None = None
    odom_accum_m: float = 0.0
    debug_next_log_t: float = 0.0

    def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371000.0
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
        return 2 * R * asin(math.sqrt(max(0.0, a)))

    # Seguimiento de último anuncio de límite (snapshot crudo)
    pending_limit = None  # dict con {"limit_next_kmh","odom_m","time","lat","lon"}

    # Señal del último evento escrito para de-dup
    last_sig = None  # (type, marker_or_station, time)

    # Mantener UN solo generador — el ritmo ya lo gobierna RDClient.stream()
    for row in rd.stream():
        # Auto-stop por tiempo si se indico
        if stop_time and time.time() >= stop_time:
            break
        now = time.time()
        row["t_wall"] = now
        # ---- enriquecer: odómetro/velocidad si faltan ----
        # Preferencias de keys de posición: lat/lon en grados si existen (fila o meta)
        meta = row.get("meta") or {}
        lat = row.get("lat") or row.get("lat_deg") or meta.get("lat") or meta.get("lat_deg")
        lon = row.get("lon") or row.get("lon_deg") or meta.get("lon") or meta.get("lon_deg")
        t_wall = float(row.get("t_wall") or 0.0)
        odom_m = row.get("odom_m")
        speed_kph = row.get("speed_kph")

        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and prev_t is not None and prev_lat is not None and prev_lon is not None:
            dt = max(1e-3, t_wall - prev_t)
            d = _haversine_m(float(prev_lat), float(prev_lon), float(lat), float(lon))
            # descartar picos imposibles (>150 m en dt de 0.2 s ~ >2700 km/h)
            if d <= 150.0:
                odom_accum_m += d
                if speed_kph in (None, "", 0, 0.0):
                    speed_kph = (d / dt) * 3.6
        elif (speed_kph not in (None, "", 0, 0.0)) and prev_t is not None:
            # fallback: integrar por velocidad si no hay lat/lon
            try:
                v = float(speed_kph) / 3.6
                dt = max(1e-3, t_wall - prev_t)
                odom_accum_m += v * dt
            except Exception:
                pass

        # clamp y asignación a la fila si faltaban
        if odom_m in (None, "", 0, 0.0):
            row["odom_m"] = float(round(odom_accum_m, 3))
        if speed_kph not in (None, ""):
            try:
                row["speed_kph"] = float(max(0.0, min(400.0, float(speed_kph))))
            except Exception:
                pass

        # actualizar estado
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            prev_lat, prev_lon = float(lat), float(lon)
        prev_t = t_wall

        # log de salud (cada ~1 s)
        if time.time() >= debug_next_log_t:
            try:
                print(f"[collector] t={t_wall:.3f} odom={row.get('odom_m')} speed={row.get('speed_kph')}")
            except Exception:
                pass
            debug_next_log_t = time.time() + 1.0

        # ---- escritura ----
        csvlog.write_row(row)
        # Robustez: SQLite con retry y fallback automático
        fallback_mode = False
        sqlite_retry_count = 3
        sqlite_retry_delay = 0.1
        error_count = 0
        if store is not None and not fallback_mode:
            for attempt in range(sqlite_retry_count):
                try:
                    store.insert_row(row)
                    if attempt > 0:
                        error_count = max(0, error_count - 1)
                    break
                except Exception as e:
                    if attempt < sqlite_retry_count - 1:
                        delay = sqlite_retry_delay * (2 ** attempt)
                        time.sleep(delay)
                    else:
                        print(f"[collector] SQLite insert failed after {sqlite_retry_count} attempts: {e}")
                        fallback_mode = True
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
                    e["time"] = h + m / 60.0 + s / 3600.0
                except Exception:
                    pass
            # Sellos siempre presentes para downstream (normalizer/analizadores)
            e["odom_m"] = odom_m
            e["t_wall"] = now

            # De-dup básico: mismo tipo+identificador+tiempo ⇒ no reescribir
            ident = e.get("marker") or e.get("name") or e.get("station") or e.get("payload")
            sig = (e.get("type"), ident, e.get("time"))
            if sig == last_sig:
                drained += 1
                continue
            last_sig = sig
            # Skip incomplete marker events lacking coordinates
            if e.get("type") == "marker_pass" and (e.get("lat") in (None, "") or e.get("lon") in (None, "")):
                drained += 1
                continue
            # --- logica de alcance de limite (estimado)
            # Normaliza SIEMPRE el evento actual antes de ramificar
            nrm = normalize(e)
            # Sello de seguridad: si algún evento viene sin t_wall, estampar ahora
            if nrm.get("t_wall") is None:
                nrm["t_wall"] = now
            # Si llega un speed_limit_change nuevo y habia uno pendiente,
            # consideramos que acabamos de "alcanzar" la placa del pendiente.
            if nrm.get("type") == "speed_limit_change":
                prev = pending_limit
                if prev:
                    dist = float(odom_m or 0.0) - float(prev.get("odom_m") or 0.0)  # distancia por odometro
                    reach = {
                        "type": "limit_reached",
                        "limit_kmh": prev["limit_next_kmh"],
                        "time": e.get("time"),
                        "lat": e.get("lat"),
                        "lon": e.get("lon"),
                        "odom_m": odom_m,
                        "dist_m_travelled": dist,
                    }
                    # Distancia geodésica (Haversine) si hay coordenadas
                    try:
                        plat, plon = prev.get("lat"), prev.get("lon")  # type: ignore[assignment]
                        clat, clon = e.get("lat"), e.get("lon")
                        if (plat is not None) and (plon is not None) and (clat is not None) and (clon is not None):
                            R = 6371000.0
                            p1, p2 = math.radians(float(plat)), math.radians(float(clat))
                            dphi = p2 - p1
                            dl = math.radians(float(clon) - float(plon))
                            a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
                            reach["dist_geo_m"] = 2 * R * math.asin(math.sqrt(a))
                    except Exception:
                        pass
                    # Anti-ruido: ignora si avance < 5 m
                    if dist >= 5.0:
                        rn = normalize(reach)
                        # Sello de seguridad: si el evento carece de t_wall, estampar ahora
                        if rn.get("t_wall") is None:
                            rn["t_wall"] = now
                        with open(EVT_PATH, "a", encoding="utf-8") as f:
                            f.write(json.dumps(rn, ensure_ascii=False) + "\n")
                pending_limit = {
                    "limit_next_kmh": nrm["limit_next_kmh"],
                    "odom_m": odom_m,
                    "time": e.get("time"),
                    "lat": e.get("lat"),
                    "lon": e.get("lon"),
                }
            else:
                # nrm ya calculado arriba
                pass
            with open(EVT_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(nrm, ensure_ascii=False) + "\n")
            drained += 1


if __name__ == "__main__":
    import argparse
    import time as _t
    import sys as _sys

    ap = argparse.ArgumentParser()
    ap.add_argument("--hz", type=float, default=12.0, help="Frecuencia objetivo (Hz)")
    ap.add_argument("--duration", type=float, default=0.0, help="Segundos hasta auto-salida (0=infinito)")
    ap.add_argument(
        "--bus-from-start",
        action="store_true",
        help="Leer el bus LUA desde el inicio (por defecto, solo nuevas líneas)",
    )
    args = ap.parse_args()
    end_t = (_t.time() + args.duration) if args.duration > 0 else None
    try:
        run(args.hz, stop_time=end_t, bus_from_start=args.bus_from_start)
    except KeyboardInterrupt:
        print("[collector] interrupción del usuario — saliendo limpio.")
        _sys.exit(0)

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
