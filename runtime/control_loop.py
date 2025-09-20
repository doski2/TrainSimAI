from __future__ import annotations
import os
import time
import sqlite3
import argparse
import json
import math
from dataclasses import replace
from pathlib import Path
from typing import Optional, Dict
import logging
from runtime.braking_v0 import BrakingConfig
from runtime.braking_era import EraCurve
from runtime.profiles import load_braking_profile, load_profile_extras
from runtime.guards import RateLimiter, JerkBrakeLimiter, overspeed_guard
from runtime.csv_logger import CSVLogger
from storage.run_store_sqlite import RunStore
from runtime.mode_guard import ModeGuard
from runtime.actuators import scan_for_rd, send_to_rd, debug_trace, load_rd_from_spec

# Fix: Añadir clases stub para evitar errores de imports
try:
    from runtime.event_stream import NonBlockingEventStream  # type: ignore
except ImportError:
    try:
        from ingestion.event_stream import NonBlockingEventStream  # type: ignore
    except ImportError:
        class NonBlockingEventStream:
            def __init__(self, *args, **kwargs):
                pass
            def poll(self):
                return None
            def __iter__(self):
                return self
            def __next__(self):
                raise StopIteration

try:
    from runtime.pid import SplitPID  # type: ignore
except ImportError:
    class SplitPID:
        def __init__(self, *args, **kwargs):
            self.kp = kwargs.get("kp", 0.0)
            self.ki = kwargs.get("ki", 0.0)
            self.kd = kwargs.get("kd", 0.0)
            self._i = 0.0
            self._prev = None
        def update(self, error: float, dt: float) -> float:
            if dt <= 0:
                return 0.0
            self._i += error * dt
            d = 0.0 if self._prev is None else (error - self._prev) / dt
            self._prev = error
            return self.kp * error + self.ki * self._i + self.kd * d

# Fix: Variables globales para FSM
_active_limit_kph: float | None = None
_last_dist_next_m: float | None = None

class ControlLoop:
    """Fix: Clase ControlLoop simplificada y corregida"""
    def __init__(self, source: str, profile=None, hz=5, db_path=None, run_csv=None, **kwargs):
        self.source = source
        self.profile = profile
        self.hz = hz
        self.db_path = db_path
        self.run_csv = run_csv
        self.running = False
        # umbral en segundos para considerar la telemetría obsoleta
        self.stale_data_threshold = float(kwargs.get("stale_data_threshold", 10.0))
        self.consecutive_failures = 0
        self.max_failures_before_fallback = 5
        self.logger = logging.getLogger(__name__)
        if source not in ['sqlite', 'csv']:
            raise ValueError(f"Invalid source: {source}")
        if source == 'sqlite' and not db_path:
            raise ValueError("db_path required for sqlite source")
        if source == 'csv' and not run_csv:
            raise ValueError("run_csv required for csv source")

    def read_telemetry(self):
        try:
            if self.source == 'sqlite':
                data = self._read_from_sqlite()
                if data and self._is_data_fresh(data):
                    self.consecutive_failures = 0
                    return data
                else:
                    self.consecutive_failures += 1
                    if self.consecutive_failures >= self.max_failures_before_fallback:
                        self.logger.warning("Too many SQLite failures, switching to CSV")
                        self.source = 'csv'
                        return self._read_from_csv()
            else:
                return self._read_from_csv()
        except Exception as e:
            self.logger.error(f"Error reading telemetry: {e}")
            self.consecutive_failures += 1
            return None

    def _read_from_sqlite(self):
        if not self.db_path:
            self.logger.error("db_path not defined")
            return None
        try:
            with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                cursor = conn.cursor()
                recent_threshold = time.time() - self.stale_data_threshold
                cursor.execute("""
                    SELECT * FROM telemetry 
                    WHERE t_wall > ? 
                    ORDER BY rowid DESC LIMIT 1
                """, (recent_threshold,))
                row = cursor.fetchone()
                if row:
                    return dict(zip([desc[0] for desc in cursor.description], row))
                cursor.execute("SELECT * FROM telemetry ORDER BY rowid DESC LIMIT 1")
                row = cursor.fetchone()
                if row:
                    data = dict(zip([desc[0] for desc in cursor.description], row))
                    age = time.time() - float(data.get('t_wall', 0))
                    self.logger.warning(f"Using stale data: {age:.1f}s old")
                    return data
        except sqlite3.OperationalError as e:
            if 'database is locked' in str(e):
                self.logger.warning(f"Database locked (attempt {self.consecutive_failures})")
                return self._read_from_csv()
            else:
                self.logger.error(f"SQLite operational error: {e}")
                raise
        except Exception as e:
            self.logger.error(f"Unexpected SQLite error: {e}")
            raise
        return None

    def _read_from_csv(self):
        if not self.run_csv:
            self.logger.error("CSV path not set")
            return None
        path = self.run_csv if isinstance(self.run_csv, str) else str(self.run_csv)
        if not os.path.exists(path):
            self.logger.error(f"CSV file not found: {path}")
            return None
        try:
            with open(path, 'r') as f:
                lines = f.readlines()
                if len(lines) < 2:
                    self.logger.warning("CSV file has no data rows")
                    return None
                header = lines[0].strip().split(',')
                last_line = lines[-1].strip().split(',')
                if len(header) != len(last_line):
                    self.logger.error("CSV header/data mismatch")
                    return None
                data: Dict[str, str] = dict(zip(header, last_line))
                for key in ['t_wall', 'odom_m', 'speed_kph']:
                    if key in data:
                        try:
                            # mantener strings para compatibilidad; conversiones posteriores harán float()
                            data[key] = str(float(data[key]))
                        except (ValueError, TypeError):
                            self.logger.warning(f"Invalid numeric value for {key}: {data[key]}")
                            data[key] = "0.0"
                return data
        except Exception as e:
            self.logger.error(f"Error reading CSV: {e}")
            return None

    def _is_data_fresh(self, data) -> bool:
        if not data or 't_wall' not in data:
            return False
        try:
            age = time.time() - float(data['t_wall'])
            return age < self.stale_data_threshold
        except (ValueError, TypeError):
            return False

    def is_data_stale(self, data) -> bool:
        """Heurística para identificar telemetría obsoleta.

        Devuelve True si:
        - falta `t_wall` en `data`, o
        - la edad calculada (time.time() - t_wall) > stale_data_threshold, o
        - el dt desde la última lectura (si `self._last_t_seen`) excede 2×threshold (salto temporal).
        """
        if not data or 't_wall' not in data:
            return True
        try:
            t = float(data['t_wall'])
        except (ValueError, TypeError):
            return True
        age = time.time() - t
        if age > self.stale_data_threshold:
            return True
        # detectar saltos grandes si tenemos última marca
        last = getattr(self, '_last_t_seen', None)
        if last is not None:
            dt = abs(t - last)
            if dt > (2.0 * self.stale_data_threshold):
                return True
        # actualizar marca
        self._last_t_seen = t
        return False

    def run(self):
        self.logger.info(f"Starting control loop - Source: {self.source}, Hz: {self.hz}")
        self.running = True
        sleep_time = 1.0 / self.hz
        try:
            while self.running:
                start_time = time.time()
                data = self.read_telemetry()
                if data:
                    # detectar datos obsoletos (stale-data)
                    try:
                        if self.is_data_stale(data):
                            age = time.time() - float(data.get("t_wall", time.time()))
                            self.logger.warning(f"stale-data detected: age={age:.1f}s > threshold={self.stale_data_threshold}s — skipping processing")
                            # aumentar contador de fallos y saltar procesamiento y envíos
                            self.consecutive_failures += 1
                            # opcional: aquí podríamos emitir un evento al EVT_PATH o CSV
                            # pero para mínima intrusión sólo registramos en logs
                        else:
                            self.consecutive_failures = 0
                            self._process_control_data(data)
                    except Exception as e:
                        self.logger.error(f"Error during stale-data check: {e}")
                        # prevenir que un fallo en la comprobación detenga el loop
                else:
                    self.logger.debug("No telemetry data available")
                elapsed = time.time() - start_time
                if elapsed < sleep_time:
                    time.sleep(sleep_time - elapsed)
        except KeyboardInterrupt:
            self.logger.info("Control loop stopped by user")
        except Exception as e:
            self.logger.error(f"Control loop error: {e}")
        finally:
            self.running = False

    def _process_control_data(self, data):
        speed = data.get('speed_kph', 0)
        odom = data.get('odom_m', 0)
        timestamp = data.get('t_wall', time.time())
        self.logger.debug(f"Processing: speed={speed} kph, odom={odom} m, t={timestamp}")

    def stop(self):
        self.running = False
def tail_csv_last_row(path: Path, max_bytes: int = 1_000_000) -> dict | None:
    """
    Lee la última fila completa de un CSV sin bloquear.
    Devuelve dict(header->valor) o None si el archivo está vacío/incompleto.
    """
    p = Path(path)
    if not p.exists():
        return None
    try:
        size = p.stat().st_size
    except Exception:
        return None
    if size < 64:
        return None
    try:
        with p.open("rb") as f:
            back = min(size, max_bytes)
            try:
                f.seek(-back, os.SEEK_END)
            except OSError:
                f.seek(0)
            chunk = f.read().decode("utf-8", errors="ignore")
    except Exception:
        return None
    lines = [ln for ln in chunk.splitlines() if ln.strip()]
    if len(lines) < 2:
        return None
    # detectar delimitador en la cabecera: preferir coma, si no existe usar punto y coma
    header_line = lines[0].strip()
    if "," in header_line:
        delim = ","
    elif ";" in header_line:
        delim = ";"
    else:
        delim = ","
    header = [h.strip().lower() for h in header_line.split(delim)]
    for last in reversed(lines[1:]):
        fields = [c.strip() for c in last.split(delim)]
        if len(fields) == len(header):
            return dict(zip(header, fields))
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


# --- utilidades físicas simples ---
def _kph_to_mps(kph: float) -> float:
    return kph / 3.6


def _brake_distance_m(v_kph: float, v_target_kph: float, a_mps2: float, t_react_s: float) -> float:
    """Distancia necesaria para pasar de v -> v_target con deceleración de servicio + tiempo de reacción."""
    v = max(0.0, _kph_to_mps(v_kph))
    vt = max(0.0, _kph_to_mps(v_target_kph))
    dv = max(0.0, v - vt)
    if a_mps2 <= 1e-6:
        return float("inf")
    d_react = t_react_s * dv
    d_brake = max(0.0, (v * v - vt * vt) / (2.0 * a_mps2))
    return d_react + d_brake


def _map_a_req_to_brake(a_req: float, a_service: float) -> float:
    """Mapea una aceleración requerida (a_req, m/s2) a un mando de freno en [0,1].

    Se preserva la ganancia suave usada en el control: 0.4 + 0.9*(a_req / max(0.1,a_service)),
    y se limita a [0,1]. Esta función facilita pruebas unitarias.
    """
    try:
        a_req_v = float(a_req)
        a_srv = max(0.1, float(a_service))
    except Exception:
        return 0.0
    val = 0.4 + 0.9 * (a_req_v / a_srv)
    if val < 0.0:
        return 0.0
    if val > 1.0:
        return 1.0
    return val


def main() -> None:
    p = argparse.ArgumentParser(description="Control online a partir de run.csv y eventos")
    p.add_argument("--run", type=Path, default=Path("data/runs/run.csv"))
    p.add_argument("--events", type=Path, default=Path("data/events.jsonl"))
    p.add_argument(
        "--emit-active-limit", action="store_true", help="Incluye columna active_limit_kph en la salida CSV"
    )
    p.add_argument(
        "--bus", default="data/lua_eventbus.jsonl", help="Event bus JSONL (fallback si events.jsonl no avanza)"
    )
    p.add_argument("--out", type=Path, default=Path("data/run.ctrl_online.csv"))
    p.add_argument("--hz", type=float, default=5.0)
    p.add_argument(
        "--rd",
        default=os.environ.get("TSC_RD", ""),
        help="Proveedor RD en formato 'modulo:atributo' (p.ej. runtime.raildriver_stub:rd). "
             "Si es callable, se invoca sin args y se usa el retorno.",
    )
    p.add_argument("--db", default="data/run.db")
    p.add_argument("--source", choices=["sqlite", "csv"], default="sqlite")
    p.add_argument("--no-csv-fallback", action="store_true", help="Desactiva fallback a CSV si SQLite está vacío")
    p.add_argument(
        "--derive-speed-if-missing",
        action="store_true",
        default=True,
        help="Si falta speed_kph, derivarla de odom_m (por defecto: activado)",
    )
    p.add_argument(
        "--no-derive-speed", action="store_true", help="Desactiva la derivación automática de speed_kph si falta"
    )
    p.add_argument("--profile", type=str, default=None)
    p.add_argument("--era-curve", type=str, default=None)
    p.add_argument("--start-events-from-end", action="store_true", help="Empezar a leer events.jsonl desde el final")
    p.add_argument("--duration", type=float, default=0.0, help="Segundos hasta auto-salida (0 = infinito)")
    # Overrides CLI (opcionales)
    p.add_argument("--A", type=float, default=None)
    p.add_argument("--margin-kph", type=float, default=None)
    p.add_argument("--rise-per-s", type=float, default=None, help="Velocidad de subida del freno (por defecto en código)")
    p.add_argument("--fall-per-s", type=float, default=None, help="Velocidad de bajada del freno (por defecto en código)")
    p.add_argument("--startup-gate-s", type=float, default=None, help="Segundos de compuerta de arranque (por defecto 4.0)")
    p.add_argument("--hold-s", type=float, default=None, help="Segundos de retención mínima al encender freno (por defecto 0.5)")
    p.add_argument("--reaction", type=float, default=None)
    p.add_argument(
        "--mode",
        choices=["full", "brake", "advisory"],
        default=os.environ.get("TSC_MODE", "brake"),
        help="Modo de actuación: full=acel+freno, brake=solo freno (tú aceleras), advisory=solo consejo (no envía comandos). Por defecto, TSC_MODE env var o 'brake'.",
    )
    args = p.parse_args()
    mode_guard = ModeGuard(args.mode)
    # declarar globals que mantienen estado entre iteraciones
    global _active_limit_kph, _last_dist_next_m
    debug_trace(False, f"[control] mode={args.mode}")
    # Debug RD: reset de log salvo que se pida append
    debug_on = os.getenv("TSC_RD_DEBUG", "0") in ("1", "true", "True")
    force_reset = os.getenv("TSC_RD_LOG_RESET", "0") in ("1", "true", "True")
    append = os.getenv("TSC_RD_LOG_APPEND", "0") in ("1", "true", "True")
    if (debug_on or force_reset) and not append:
        Path("data").mkdir(parents=True, exist_ok=True)
        Path("data").joinpath("rd_send.log").open("w").close()
    # RD preferente por --rd/TSC_RD
    rd_spec = args.rd
    rd_static, rd_where = load_rd_from_spec(rd_spec)
    if rd_static:
        debug_trace(False, f"[control] rd provider: {rd_where}")

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
    # Estado para suavizado ligero y flag de approach (estado local, no usar self.* en función)
    v_filt_kph_state: Optional[float] = None
    approach_active: bool = False
    # PID instanciado una vez (no por cada iteración)
    pid = SplitPID()

    # Estado para control de freno (histéresis + retención + rampa)
    _brake_on: bool = False
    _brake_hold_until: float = 0.0
    _brake_cmd: float = 0.0
    _last_t_for_brake: float = 0.0

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
            "speed_filt_kph",
            "next_limit_kph",
            "next_limit_used_kph",
            "cur_limit_used_kph",
            "dist_next_limit_m",
            "target_speed_kph",
            "phase",
            "throttle",
            "brake",
            "approach_active",
            "control_ready",
        ],
    )

    # Fuente de datos opcional: SQLite
    store = RunStore(args.db) if args.source == "sqlite" else None
    last_rowid = 0
    use_csv = args.source == "csv"
    # Robustez: control de fallos y datos obsoletos
    stale_data_threshold = 10.0  # segundos
    consecutive_failures = 0
    max_failures_before_fallback = 5
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
    # tiempo de inicio según t_wall (para compuerta de arranque)
    start_t_wall: float | None = None

    period = 1.0 / max(0.5, float(args.hz))
    t0 = time.perf_counter()
    t_next = t0
    # Control debug guard (set TSC_CTRL_DEBUG=1 to enable per-cycle debug prints)
    ctrl_debug = os.getenv("TSC_CTRL_DEBUG", "0") in ("1", "true", "True")

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
            # Robustez: leer con detección de datos obsoletos y fallback
            try:
                latest = store.latest_since(last_rowid)
                if latest is None:
                    consecutive_failures += 1
                    if not args.no_csv_fallback and consecutive_failures >= max_failures_before_fallback:
                        print("[control] Demasiados fallos en SQLite, cambiando a CSV.")
                        use_csv = True
                    time.sleep(0.05)
                    continue
                else:
                    last_rowid, row = latest
                    # Verificar frescura de los datos
                    t_wall_val = _to_float_loose(row.get("t_wall", ""))
                    age = time.time() - t_wall_val if t_wall_val else 9999
                    if age > stale_data_threshold:
                        consecutive_failures += 1
                        print(f"[control] Datos obsoletos de SQLite: {age:.1f}s, fallo {consecutive_failures}")
                        if not args.no_csv_fallback and consecutive_failures >= max_failures_before_fallback:
                            print("[control] Cambiando a CSV por datos obsoletos.")
                            use_csv = True
                        time.sleep(0.05)
                        continue
                    else:
                        consecutive_failures = 0
            except Exception as e:
                consecutive_failures += 1
                print(f"[control] Error leyendo SQLite: {e}")
                if not args.no_csv_fallback and consecutive_failures >= max_failures_before_fallback:
                    print("[control] Cambiando a CSV por errores consecutivos.")
                    use_csv = True
                time.sleep(0.05)
                continue
        if use_csv:
            # Reanudar desde la última fila (solo si el CSV ya tiene contenido)
            if os.path.exists(run_path) and os.path.getsize(run_path) >= 128:
                row = tail_csv_last_row(run_path)
            else:
                row = None
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

        # --- suavizado ligero para control (no para ocultar errores de sensado) ---
        alpha = 0.25  # 0<alpha<=1; menor = más suave
        if v_filt_kph_state is None:
            v_filt_kph_state = float(speed_kph) if (speed_kph is not None and not math.isnan(speed_kph)) else 0.0
        else:
            sf = float(speed_kph) if (speed_kph is not None and not math.isnan(speed_kph)) else v_filt_kph_state
            v_filt_kph_state = alpha * sf + (1 - alpha) * v_filt_kph_state
        v_for_control_kph = v_filt_kph_state

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

        # --- FSM de límite activo -------------------------------------------------
        # Si cruzamos la baliza del próximo límite (dist pasa de >0 a <=0), el
        # límite activo pasa a ser el del próximo.
        try:
            dn = None if dist_next_limit_m is None else float(dist_next_limit_m)
            nl = None if next_limit_kph is None else float(next_limit_kph)
        except Exception:
            dn, nl = None, None
        if _last_dist_next_m is not None and dn is not None:
            if _last_dist_next_m > 0.0 and dn <= 0.0 and nl is not None:
                _active_limit_kph = nl
        _last_dist_next_m = dn

        # 3.1) Si ya estamos "en" el hito (distances cercanas a 0), promover el límite a 'activo'
        if dist_next_limit_m is not None and dist_next_limit_m <= 2.0:
            try:
                # promover a variable de módulo persistente
                _active_limit_kph = float(next_limit_kph) if next_limit_kph is not None else _active_limit_kph
            except Exception:
                pass
            # limpiar el próximo límite y su anclaje
            next_limit_kph = None
            anchor_dist_m = None
            anchor_odom_m = None
            dist_next_limit_m = None
            last_dist_m = None
            last_limit_kph = None

        # --- compuerta de arranque: sin límites válidos, no frenar ---
        # inicializar start_t_wall la primera vez que tengamos t_wall válido
        if start_t_wall is None:
            start_t_wall = float(t_wall)
        t_since = float(t_wall) - float(start_t_wall)
        limits_valid = (active_limit_kph is not None and not math.isnan(float(active_limit_kph))) or (
            next_limit_kph is not None and dist_next_limit_m is not None
        )
        # compuerta de arranque: puede sobreescribirse por CLI
        startup_gate_s = float(args.startup_gate_s) if args.startup_gate_s is not None else 4.0
        control_ready = (t_since >= startup_gate_s) and bool(limits_valid)

        # 4) objetivo y PID (lógica 'approach' conservadora basada en distancia física)
        # Resolver parámetros físicos y de perfil (compatibilidad con nombres antiguos)
        v_margin_kph = float(getattr(cfg, "v_margin_kph", getattr(cfg, "margin_kph", 3.0)))
        a_service = float(getattr(cfg, "a_service_mps2", getattr(cfg, "max_service_decel", 0.7)))
        t_react = float(getattr(cfg, "t_react_s", getattr(cfg, "reaction_time_s", 0.6)))
        margin_m = float(extras.get("margin_m", 0.0) if isinstance(extras, dict) else 0.0)

        # Crucero por defecto: si hay límite activo, lo usamos con margen; si no, mantenemos velocidad actual
        cruise_kph = speed_kph
        if _active_limit_kph is not None:
            cruise_kph = max(0.0, float(_active_limit_kph) - v_margin_kph)

        target_next_kph = None
        if next_limit_kph is not None:
            target_next_kph = max(0.0, float(next_limit_kph) - v_margin_kph)

        if next_limit_kph is None or dist_next_limit_m is None:
            # No hay siguiente límite -> mantén crucero del límite actual o velocidad actual
            v_tgt = cruise_kph
            phase = "CRUISE" if (speed_kph is not None and v_tgt >= speed_kph - 0.1) else "COAST"
            approach_active = False
        else:
            # Distancia que necesitamos para llegar a target_next_kph con seguridad
            # Asegurar tipos válidos
            v_use = float(v_for_control_kph if v_for_control_kph is not None else (speed_kph if speed_kph is not None else 0.0))
            tgt = float(target_next_kph if target_next_kph is not None else 0.0)
            d_need = _brake_distance_m(v_use, tgt, a_service, t_react) + margin_m

            # Histeresis para evitar oscilaciones (10%)
            prev = approach_active
            if dist_next_limit_m < d_need * 0.9:
                approach = True
            elif dist_next_limit_m > d_need * 1.1:
                approach = False
            else:
                approach = prev
            approach_active = approach

            if approach:
                v_tgt = target_next_kph if target_next_kph is not None else 0.0
                phase = "BRAKE" if (speed_kph is not None and v_tgt < speed_kph - cfg.coast_band_kph) else "COAST"
            else:
                v_tgt = cruise_kph
                phase = "CRUISE" if (speed_kph is not None and v_tgt >= speed_kph - 0.1) else "COAST"

        # Failsafe: si algo devolviera NaN o None, usar velocidad actual
        try:
            if v_tgt is None or not (float(v_tgt) == float(v_tgt)):
                raise ValueError
        except Exception:
            v_tgt = float(speed_kph) if (speed_kph is not None) else 0.0
            phase = "CRUISE"

        # SplitPID.update espera (error, dt); aquí error = v_tgt - speed_kph
        # Asegurar que speed_kph y v_tgt son floats válidos
        sp = float(speed_kph) if (speed_kph is not None and not math.isnan(speed_kph)) else 0.0
        tgt_err = float(v_tgt) - sp
        pid_out = pid.update(tgt_err, period)
        # Si el PID real devuelve una tupla (th, br), descomponer; si es float, usar como throttle y brake=0
        if isinstance(pid_out, tuple) and len(pid_out) == 2:
            th, br = pid_out
        else:
            th, br = pid_out, 0.0
        # aplicar rate limiters
        th = rl_th.step(th, period)
        # overspeed guard (mínimo de freno) — aplicamos al próximo si existe, si no al activo
        # overspeed_guard comparará contra next_limit_kph si está disponible, o bien contra _active_limit_kph
        og = overspeed_guard(
            float(speed_kph) if speed_kph is not None else 0.0,
            float(next_limit_kph) if next_limit_kph is not None else (_active_limit_kph if _active_limit_kph is not None else 0.0),
        )

        # 4.1) Guard FÍSICO por distancia (a_req > a_service -> pisar más freno)
        try:
            a_service = float(getattr(cfg, "a_service_mps2", 0.6))
            if dist_next_limit_m is not None and next_limit_kph is not None:
                v = max(0.0, float(speed_kph if speed_kph is not None else 0.0)) / 3.6
                vlim = max(0.0, float(next_limit_kph)) / 3.6
                d = max(1.0, float(dist_next_limit_m))  # evita div/0
                a_req = max(0.0, (v * v - vlim * vlim) / (2.0 * d))
                if a_req > 0.70 * a_service:
                    phase = "BRAKE"
                    # mapear (a_req / a_service) a mando de freno (0..1), con ganancia suave
                    br = max(br, _map_a_req_to_brake(a_req, a_service))
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
            "speed_filt_kph": float(v_for_control_kph),
            "next_limit_kph": "" if next_limit_kph is None else float(next_limit_kph),
            "next_limit_used_kph": "" if next_limit_kph is None else float(next_limit_kph),
            "cur_limit_used_kph": float(_active_limit_kph) if _active_limit_kph is not None else float("nan"),
            "dist_next_limit_m": "" if dist_next_limit_m is None else float(dist_next_limit_m),
            "target_speed_kph": float(v_tgt),
            "phase": phase,
            "throttle": float(round(th, 3)),
            "brake": float(round(br, 3)),
            "control_ready": int(bool(control_ready)),
        }
        row_out["approach_active"] = int(bool(approach_active))
        if getattr(args, "emit_active_limit", False):
            row_out["active_limit_kph"] = _active_limit_kph if _active_limit_kph is not None else ""
        # --- control de freno con histéresis + retención + rampa hacia "desired" ---
        # desired_brake: lo que pide el PID/guard como mínimo efectivo
        desired_brake = max(0.0, float(br))
        # error respecto al objetivo (positivo => vamos "pasados")
        err_kph = max(0.0, float(v_for_control_kph) - float(v_tgt))
        on = _brake_on
        # Schmitt (evita aleteo): enciende con >0.7 kph; apaga con <0.3 kph
        if err_kph > 0.7:
            on = True
        elif err_kph < 0.3:
            on = False
        # Si el guard/phys pide freno, lo consideramos "on"
        if desired_brake > 0.05:
            on = True
        # no frenar en crucero si no estamos en aproximación y vamos por debajo de cruise + 0.3
        # pero no cancelar el encendido si un guard físico/por distancia ya pide freno
        if desired_brake <= 0.05 and (not approach_active and float(v_for_control_kph) <= (float(cruise_kph) + 0.3)):
            on = False
        # compuerta de arranque: hasta que el control esté "ready" NO se permite
        # frenar por control, pero si un guard físico/por distancia ya pide freno
        # (desired_brake > 0.05) lo permitimos. Esto evita que la compuerta inicial
        # suprima órdenes de emergencia o guardias físicos.
        if not bool(control_ready) and desired_brake <= 0.05:
            on = False

        now = float(row_out["t_wall"])
        hold_s = float(args.hold_s) if args.hold_s is not None else 0.5
        hold_until = _brake_hold_until
        if on:
            # al encender, garantizamos 0.5 s de retención mínima
            hold_until = max(hold_until, now + hold_s)
        _brake_hold_until = hold_until
        if now < hold_until:
            on = True
        _brake_on = on

        # rampa suave de mando hacia el objetivo (desired si on, 0 si off)
        brake_cmd_local = _brake_cmd
        # Proteger contra _last_t_for_brake no inicializado o mezcla de orígenes de tiempo
        # Si _last_t_for_brake <= 0 (valor inicial) o la diferencia es irracionalmente grande,
        # usamos el periodo de control como fallback para evitar saltos gigantes en la rampa.
        try:
            if _last_t_for_brake is None or _last_t_for_brake <= 0.0:
                dt_br = period
            else:
                raw_dt = now - _last_t_for_brake
                # Si raw_dt es <=0 (muestras fuera de orden) o excesivamente grande (>10s), clamp
                if raw_dt <= 0.0 or raw_dt > 10.0:
                    dt_br = period
                else:
                    dt_br = raw_dt
        except Exception:
            dt_br = period
        dt_br = max(1e-3, float(dt_br))
        _last_t_for_brake = now
        rise_per_s = float(args.rise_per_s) if args.rise_per_s is not None else 1.2
        fall_per_s = float(args.fall_per_s) if args.fall_per_s is not None else 2.0
        target_brake = desired_brake if on else 0.0
        if ctrl_debug:
            try:
                print(f"[CTRL-DBG] t={now:.3f} err_kph={err_kph:.3f} desired_brake(before_ramp)={desired_brake:.3f} on={on}")
            except Exception:
                pass
        delta = target_brake - brake_cmd_local
        if delta >= 0.0:
            brake_cmd_local = min(1.0, brake_cmd_local + min(delta, rise_per_s * dt_br))
        else:
            brake_cmd_local = max(0.0, brake_cmd_local + max(delta, -fall_per_s * dt_br))
        if ctrl_debug:
            try:
                print(f"[CTRL-DBG] t={now:.3f} brake_cmd(after_ramp)={brake_cmd_local:.3f} dt_br={dt_br:.3f}")
            except Exception:
                pass
        # Trazas compactas por ciclo para diagnóstico (JSONL en data/ctrl_cycle.log)
        if ctrl_debug:
            try:
                cycle = {
                    "t_wall": now,
                    "err_kph": float(err_kph),
                    "desired_brake": float(desired_brake),
                    "on": bool(on),
                    "approach_active": bool(approach_active),
                    "v_for_control_kph": float(v_for_control_kph),
                    "cruise_kph": float(cruise_kph),
                    "control_ready": bool(control_ready),
                    "hold_until": float(_brake_hold_until),
                    "last_t_for_brake": float(_last_t_for_brake),
                    "dt_br": float(dt_br),
                    "brake_cmd_after": float(brake_cmd_local),
                }
                Path("data").mkdir(parents=True, exist_ok=True)
                with Path("data/ctrl_cycle.log").open("a", encoding="utf-8") as _f:
                    _f.write(json.dumps(cycle) + "\n")
            except Exception:
                pass
        _brake_cmd = brake_cmd_local

        # aplicar en modo brake (la IA no toca throttle en brake/advisory)
        row_out["throttle"] = 0.0
        row_out["brake"] = float(round(brake_cmd_local, 3))

        # === Envío condicionado por el modo ===
        throttle_cmd = th if mode_guard.mode == "full" else 0.0
        brake_cmd = brake_cmd_local
        t_send, b_send = mode_guard.clamp_outputs(throttle_cmd, brake_cmd)
        # RD: usa primero el provisto por --rd/TSC_RD; si no, intenta escaneo en locals/globals
        if rd_static is not None:
            rd_obj, rd_name = rd_static, rd_where
        else:
            rd_obj, rd_name = scan_for_rd(locals(), globals())
        debug_on = os.getenv("TSC_RD_DEBUG", "0") in ("1", "true", "True")
        if rd_obj is None:
            debug_trace(debug_on, f"NO-RD mode={mode_guard.mode} t_plan={throttle_cmd} b_plan={brake_cmd}")
        else:
            if ctrl_debug:
                try:
                    print(f"[CTRL-DBG] about to send_to_rd rd={rd_name} mode={mode_guard.mode} send(t={t_send},b={b_send})")
                except Exception:
                    pass
            thr_ok, brk_ok, thr_m, brk_m = send_to_rd(rd_obj, t_send, b_send)
            debug_trace(
                debug_on,
                f"RD={rd_name} mode={mode_guard.mode} "
                f"plan(t={throttle_cmd},b={brake_cmd}) send(t={t_send},b={b_send}) "
                f"applied(thr={thr_ok}:{thr_m}, brk={brk_ok}:{brk_m})"
            )
        # log CSV (PLAN): se mantiene igual, independientemente del modo de envío
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
