from __future__ import annotations

import logging
import os
import platform
import re
import struct
import sys
import time
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Thread
from typing import Any, Dict, Iterable, Iterator, List, Optional

# Optional Prometheus metrics (do not hard-fail if library missing)
try:
    from prometheus_client import Counter, Gauge, Histogram  # type: ignore

    RD_SET_CALLS = Counter("trainsim_rd_set_calls_total", "Number of RD set calls")
    RD_ERRORS = Counter("trainsim_rd_errors_total", "Number of RD errors")
    RD_MISSING = Counter(
        "trainsim_rd_missing_control_total",
        "Number of attempts to set missing controls",
    )
    RD_ACKS = Counter("trainsim_rd_acks_total", "Number of RD acks observed")
    RD_RETRIES = Counter(
        "trainsim_rd_retries_total", "Number of RD retries due to missing ack or errors"
    )
    RD_EMERGENCY = Counter(
        "trainsim_rd_emergencystops_total", "Number of emergency stops triggered"
    )
    RD_ACK_LATENCY = Histogram(
        "trainsim_rd_ack_latency_seconds", "Ack latency in seconds"
    )
    RD_EMERGENCY_GAUGE = Gauge(
        "trainsim_rd_emergency_state", "Current emergency state (0/1)"
    )
except Exception:
    RD_SET_CALLS = None  # type: ignore
    RD_ERRORS = None  # type: ignore
    RD_MISSING = None  # type: ignore
    RD_ACKS = None  # type: ignore
    RD_RETRIES = None  # type: ignore
    RD_EMERGENCY = None  # type: ignore
    RD_ACK_LATENCY = None  # type: ignore
    RD_EMERGENCY_GAUGE = None  # type: ignore


# Optionally start an HTTP exporter if user enables via env var


def _maybe_start_prometheus_exporter() -> None:
    port = os.getenv("TSC_PROMETHEUS_PORT")
    if not port:
        return
    try:
        from prometheus_client import start_http_server  # type: ignore

        try:
            p = int(port)
        except Exception:
            # allow service name or invalid int -> ignore
            try:
                p = int(os.getenv("TSC_PROMETHEUS_PORT", "0"))
            except Exception:
                return
        try:
            start_http_server(p)
            logging.getLogger("ingestion.rd_client").info(
                "Prometheus exporter started on port %s", p
            )
        except Exception:
            logging.getLogger("ingestion.rd_client").exception(
                "Failed to start Prometheus exporter on %s", p
            )
    except Exception:
        # prometheus_client not available or import failed
        return


def _norm_ctrl_name(name: str) -> str:
    """Normaliza un nombre de control para comparación robusta.

    - lower-case
    - quita sufijo 'hz'
    - elimina caracteres no alfanuméricos
    """
    if not name:
        return ""
    s = name.lower()
    s = s.replace("hz", "")
    s = re.sub(r"[^a-z0-9]", "", s)
    return s


def _load_suggested_aliases() -> Dict[str, List[str]]:
    """Carga `profiles/suggested_aliases.json` si existe, devuelve dict vacío si no."""
    try:
        p = Path(__file__).resolve().parents[1] / "profiles" / "suggested_aliases.json"
        if p.exists():
            import json as _json

            with p.open("r", encoding="utf-8") as fh:
                return _json.load(fh)
    except Exception:
        pass
    return {}


# NOTE: Starting an HTTP exporter at module import can cause surprising side-effects
# (server started on import). We prefer to start it explicitly when the runtime
# is constructed (RDClient.__init__) so tests and importers aren't affected.


def _ensure_raildriver_on_path() -> None:
    """
    Añade el paquete local `py-raildriver-master` al sys.path si existe
    junto al repo, para poder `import raildriver` sin instalación previa.
    """
    here = Path(__file__).resolve().parent
    candidate = here.parent / "py-raildriver-master"
    if candidate.exists():
        sys.path.insert(0, str(candidate))


_ensure_raildriver_on_path()

# Importa RailDriver y Listener del paquete local
USE_FAKE = False
try:
    from raildriver import RailDriver  # type: ignore  # noqa: E402
    from raildriver.events import Listener  # type: ignore  # noqa: E402
except Exception:
    # Si no está instalado, o si se fuerza por env → usa backend simulado
    USE_FAKE = True
if not USE_FAKE:
    import os as _os

    if _os.environ.get("TSC_FAKE_RD") == "1":
        USE_FAKE = True
if USE_FAKE:
    from ingestion.rd_fake import (
        FakeListener as Listener,
    )  # type: ignore  # noqa: E402, F811
    from ingestion.rd_fake import (
        FakeRailDriver as RailDriver,
    )  # type: ignore  # noqa: E402, F811


# Claves especiales disponibles en Listener (no se suscriben; se evalúan siempre)
SPECIAL_KEYS: List[str] = list(Listener.special_fields.keys())  # type: ignore[attr-defined]


def _locate_raildriver_dll() -> str | None:
    """Selecciona la DLL que coincide con la arquitectura de Python.

    - En Python de 64 bits, preferir 'RailDriver64.dll'.
    - En Python de 32 bits, preferir 'RailDriver.dll'.
    - Busca rutas típicas de Steam; permite sobreescritura vía env RAILWORKS_PLUGINS.
    """
    wants_64 = platform.architecture()[0] == "64bit"
    candidates: list[Path] = []
    # Sobrescritura del usuario
    env_plugins = os.environ.get("RAILWORKS_PLUGINS")
    if env_plugins:
        base = Path(env_plugins)
        candidates += [base / "RailDriver64.dll", base / "RailDriver.dll"]
    # Rutas comunes de Steam
    common_bases = [
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\\Program Files (x86)"))
        / "Steam"
        / "steamapps"
        / "common"
        / "RailWorks"
        / "plugins",
        Path(os.environ.get("PROGRAMFILES", r"C:\\Program Files"))
        / "Steam"
        / "steamapps"
        / "common"
        / "RailWorks"
        / "plugins",
    ]
    # Intentar SteamPath del registro, si está disponible
    try:
        import winreg  # type: ignore

        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
        reg_base = Path(steam_path) / "steamapps" / "common" / "RailWorks" / "plugins"
        common_bases.insert(0, reg_base)
    except Exception:
        pass
    for base in common_bases:
        candidates += [base / "RailDriver64.dll", base / "RailDriver.dll"]
    # Elegir la mejor coincidencia
    existing = [p for p in candidates if p.exists()]
    if not existing:
        return None
    if wants_64:
        for p in existing:
            if p.name.lower() == "raildriver64.dll":
                return str(p)
    # Alternativa: 32 bits o la primera encontrada
    return str(existing[0])


# ---- Utilidades alternativas de localización y preparación de DLL ----


def _process_is_64bit() -> bool:
    return 8 * struct.calcsize("P") == 8


def _resolve_plugins_dir() -> Path:
    """Orden de precedencia para localizar plugins:
    1) TSC_RD_DLL_DIR  2) RAILWORKS_PLUGINS  3) ruta Steam por defecto.
    """
    p = os.getenv("TSC_RD_DLL_DIR")
    if p:
        return Path(p)
    p = os.getenv("RAILWORKS_PLUGINS")
    if p:
        return Path(p)
    return (
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\\Program Files (x86)"))
        / "Steam/steamapps/common/RailWorks/plugins"
    )


def _pick_dll_name() -> str:
    return "RailDriver64.dll" if _process_is_64bit() else "RailDriver.dll"


def _prepare_dll_search_path(base: Path) -> Path:
    """Confirma existencia de la DLL correcta y añade su carpeta al loader de Windows."""
    want = base / _pick_dll_name()
    if not want.exists():
        alt = base / ("RailDriver.dll" if _process_is_64bit() else "RailDriver64.dll")
        if alt.exists():
            arch = "64" if _process_is_64bit() else "32"
            raise OSError(
                f"RailDriver de arquitectura opuesta detectado ({alt.name}) en {alt.parent}. "
                f"Tu Python es {arch}-bit. Instala la DLL correcta o usa Python de otra arquitectura. "
                f"También puedes definir TSC_RD_DLL_DIR/RAILWORKS_PLUGINS."
            )
        raise FileNotFoundError(
            f"No se encontró {want.name} en {base}. Define RAILWORKS_PLUGINS o TSC_RD_DLL_DIR."
        )
    try:
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(str(base))  # type: ignore[attr-defined]
        else:
            os.environ["PATH"] = str(base) + os.pathsep + os.environ.get("PATH", "")
    except Exception:
        pass
    return want


class RDClient:
    """
    Wrapper de py-raildriver con utilidades de lectura puntual y streaming.

    - Usa `Listener` para obtener snapshot consistente de controles + especiales.
    - Expone utilidades para obtener un subconjunto habitual de controles.
    """

    # Class-level attribute annotations to help static analysis (attributes
    # are populated in __init__ but declaring them here avoids "unknown"
    # attribute warnings from type checkers).
    rd: Optional[object]
    listener: Optional[object]
    ctrl_index_by_name: Dict[str, int]
    _last_geo: Dict[str, Any]
    poll_dt: float
    _control_aliases: dict | None
    logger: logging.Logger

    def __init__(
        self,
        poll_dt: float = 0.2,
        poll_hz: float | None = None,
        dll_location: str | None = None,
        rd: object | None = None,
        control_aliases: dict | None = None,
        ack_watchdog: bool | int = False,
        ack_watchdog_interval: float = 0.1,
    ) -> None:
        # Permite sobrescribir por env: TSC_RD_DLL_DIR
        self.dll_location = os.getenv("TSC_RD_DLL_DIR") or dll_location
        if poll_hz and poll_hz > 0:
            self.poll_dt = 1.0 / float(poll_hz)
        else:
            self.poll_dt = float(poll_dt)
        # Logger for diagnostics
        self.logger = logging.getLogger("ingestion.rd_client")
        # Optionally inject a custom alias mapping for controls (useful for tests)
        self._control_aliases = control_aliases

        # Allow caller to inject an already-constructed RailDriver (tests, embedded)
        # If provided, use it and defer any driver-dependent initialization to
        # `attach_raildriver()`. If not provided, fall back to the previous
        # behaviour (attempt to locate and instantiate RailDriver) for
        # backward-compatibility when running on a real machine.
        self.rd = rd  # type: ignore[assignment]
        self._deferred_attach = False
        if self.rd is None:
            # Seleccionar la DLL adecuada para evitar WinError 193 (arquitecturas distintas)
            if USE_FAKE:
                # Alias RailDriver apunta al FakeRailDriver cuando USE_FAKE=True
                self.rd = RailDriver()
            else:
                # Resolver ubicación de DLL adecuada y pasarla explícitamente
                dll_path = self.dll_location or _locate_raildriver_dll()
                # Si el usuario pasó un directorio, elige el nombre correcto según arquitectura
                try:
                    if dll_path and os.path.isdir(dll_path):
                        base = Path(dll_path)
                        dll_path = str((_prepare_dll_search_path(base)))
                except Exception:
                    # Si falla (carpeta sin DLL), dejamos que el fallback actúe más abajo
                    dll_path = None
                if not dll_path:
                    # Fallback: reglas de entorno + ruta por defecto de Steam
                    try:
                        candidate = _prepare_dll_search_path(_resolve_plugins_dir())
                        dll_path = str(candidate)
                    except Exception:
                        dll_path = None
                # Diagnóstico: mostrar la DLL elegida (útil para WinError 193)
                try:
                    if dll_path:
                        self.logger.debug("using RailDriver DLL: %s", dll_path)
                except Exception:
                    self.logger.exception("error logging dll path")
                # Registrar el directorio de la DLL en el buscador de Windows (Py 3.8+)
                try:
                    if dll_path:
                        dll_dir = os.path.dirname(dll_path)
                        if dll_dir and hasattr(os, "add_dll_directory"):
                            os.add_dll_directory(dll_dir)  # type: ignore[attr-defined]
                    elif self.dll_location and hasattr(os, "add_dll_directory"):
                        os.add_dll_directory(self.dll_location)  # type: ignore[attr-defined]
                except Exception:
                    # Si falla, continuamos sin registrar ruta explícita
                    pass
                # Instanciar RailDriver indicando ruta si la conocemos; tolerar diferentes firmas
                try:
                    if dll_path:
                        try:
                            self.rd = RailDriver(dll_location=dll_path)  # type: ignore[call-arg]
                        except TypeError:
                            # Otros forks aceptan dll_path como nombre de kw
                            self.rd = RailDriver(dll_path=dll_path)  # type: ignore[call-arg]
                    else:
                        self.rd = RailDriver()
                except TypeError:
                    # Fallback posicional
                    if dll_path:
                        self.rd = RailDriver(dll_path)  # type: ignore[misc]
                    else:
                        self.rd = RailDriver()
        # Necesario para intercambiar datos con TS
        # If rd was injected we defer driver-dependent initialization until
        # `attach_raildriver()` is called. If we created the driver here, mark
        # that attach should run now.
        if self.rd is not None:
            try:
                self.rd.set_rail_driver_connected(True)  # type: ignore[attr-defined]
            except Exception:
                # Versiones antiguas ignoran el parámetro; continuamos.
                pass
        else:
            # no driver available; keep flag so attach can be used later
            self._deferred_attach = True

        # Prepare driver-independent runtime state. If a driver was injected or
        # created above, perform the driver-dependent initialization in
        # `attach_raildriver()`. This avoids constructing platform-specific
        # resources during import or in test environments.
        self.ctrl_index_by_name: Dict[str, int] = {}
        self.listener = None
        # Caché de la última geo conocida para rellenar huecos momentáneos
        self._last_geo: Dict[str, Any] = {
            "lat": None,
            "lon": None,
            "heading": None,
            "gradient": None,
        }

        # If a driver object is available now (we created it above), attach it
        # immediately; otherwise tests or consumers can call `attach_raildriver`
        # with an injected driver.
        try:
            if self.rd is not None:
                self.attach_raildriver(self.rd)
        except Exception:
            # avoid failing construction; tests can still attach later
            self.logger.exception("attach_raildriver failed during __init__")

        # Safety runtime state
        # per-control last send timestamp for rate limiting
        self._last_send_ts: Dict[str, float] = {}
        # per-control retry counts
        self._retry_counts: Dict[str, int] = {}
        # limits per control name (optional; fake driver exposes min/max)
        self._limits: Dict[str, tuple[float, float]] = {}
        # default rate limit (commands per second)
        self._rate_limit_hz = float(os.getenv("TSC_RATE_LIMIT_HZ", "5"))
        # ack/retry policy
        self._ack_timeout = float(os.getenv("TSC_ACK_TIMEOUT", "0.5"))
        self._max_retries = int(os.getenv("TSC_MAX_RETRIES", "3"))
        # emergency flag
        self._emergency_active = False

        # ACK watchdog (background confirmation): disabled by default
        self._ack_watchdog_enabled = bool(ack_watchdog)
        self._ack_watchdog_interval = float(ack_watchdog_interval)
        # queue of pending confirmations: tuples (name, expected, attempts)
        self._ack_queue: "Queue[tuple[str, float, int]]" = Queue()
        self._ack_worker_stop = Event()
        self._ack_worker: Thread | None = None
        if self._ack_watchdog_enabled:
            # start background thread
            def _ack_worker_fn():
                while not self._ack_worker_stop.is_set():
                    try:
                        name, expected, attempts = self._ack_queue.get(
                            timeout=self._ack_watchdog_interval
                        )
                    except Empty:
                        continue
                    # attempt to confirm; if not confirmed, requeue or escalate
                    confirmed = False
                    try:
                        confirmed = self._wait_for_ack(name, expected)
                    except Exception:
                        confirmed = False
                    if confirmed:
                        # Clear retries and record metric
                        try:
                            self._clear_retries(name)
                        except Exception:
                            pass
                        if RD_ACKS is not None:
                            try:
                                RD_ACKS.inc()
                            except Exception:
                                pass
                        # nothing else to do
                        continue
                    else:
                        # record a retry and requeue if attempts left
                        self._record_retry(name)
                        # escalate deterministically based on recorded retry count
                        try:
                            if self._retry_counts.get(name, 0) > self._max_retries:
                                try:
                                    self.emergency_stop("no_ack_watchdog")
                                except Exception:
                                    pass
                                continue
                        except Exception:
                            pass
                        # requeue with incremented attempts for bookkeeping
                        try:
                            self._ack_queue.put_nowait((name, expected, attempts + 1))
                        except Exception:
                            pass

            self._ack_worker = Thread(target=_ack_worker_fn, daemon=True)
            self._ack_worker.start()

    def attach_raildriver(self, rd_obj: object) -> None:
        """Perform driver-dependent initialization.

        This method can be called explicitly by tests to inject a FakeRailDriver
        or by production code after the RD is available. It's safe to call
        multiple times (idempotent-ish).
        """
        try:
            self.rd = rd_obj  # type: ignore[assignment]
            try:
                self.rd.set_rail_driver_connected(True)  # type: ignore[attr-defined]
            except Exception:
                pass
            # Build a name->index mapping explicitly so mypy can infer types
            self.ctrl_index_by_name = {}
            for idx, nm in self.rd.get_controller_list():  # type: ignore[attr-defined]
                try:
                    self.ctrl_index_by_name[str(nm)] = int(idx)
                except Exception:
                    continue
            # Listener para cambios y snapshots unificados
            try:
                self.listener = Listener(self.rd, interval=self.poll_dt)  # type: ignore[call-arg]
                try:
                    self.listener.subscribe(list(self.ctrl_index_by_name.keys()))  # type: ignore[attr-defined]
                except Exception:
                    pass
            except Exception:
                # Some driver implementations may not support Listener in tests
                self.listener = None
            # Populate limits from driver if possible
            try:
                for name in self.ctrl_index_by_name:
                    try:
                        mi = float(self.rd.get_min_controller_value(name))  # type: ignore[attr-defined]
                        ma = float(self.rd.get_max_controller_value(name))  # type: ignore[attr-defined]
                        self._limits[name] = (mi, ma)
                    except Exception:
                        continue
            except Exception:
                pass
        except Exception:
            # Best effort: don't raise from attach
            self.logger.exception("failed to attach raildriver")

    def shutdown(self) -> None:
        """Best-effort shutdown: stop ack worker and listener threads.

        Tests should call this to ensure background threads stop cleanly.
        """
        try:
            if hasattr(self, "_ack_worker_stop") and self._ack_worker_stop is not None:
                try:
                    self._ack_worker_stop.set()
                except Exception:
                    pass
            if hasattr(self, "_ack_worker") and self._ack_worker is not None:
                try:
                    # join briefly if possible
                    self._ack_worker.join(timeout=0.2)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if getattr(self, "listener", None) is not None:
                try:
                    # Listener implementations may provide a stop/close method
                    stopfn = getattr(self.listener, "stop", None)
                    if callable(stopfn):
                        stopfn()
                except Exception:
                    pass
        except Exception:
            pass

        # Start Prometheus exporter if requested via env (do it here to avoid
        # side-effects at import time in tests and tooling).
        try:
            _maybe_start_prometheus_exporter()
        except Exception:
            # don't fail __init__ if exporter fails
            pass

        # Populate limits from driver if possible
        try:
            for name in self.ctrl_index_by_name:
                try:
                    mi = float(self.rd.get_min_controller_value(name))  # type: ignore[attr-defined]
                    ma = float(self.rd.get_max_controller_value(name))  # type: ignore[attr-defined]
                    self._limits[name] = (mi, ma)
                except Exception:
                    continue
        except Exception:
            pass

    # --- Lectura mediante iteración única del listener ---
    def _snapshot(self) -> Dict[str, Any]:
        """Fuerza una iteración del listener y devuelve una copia del estado actual."""
        # No arrancamos hilo; usamos una iteración síncrona
        self.listener._main_iteration()  # type: ignore[attr-defined]
        cd = getattr(self.listener, "current_data", None)
        return dict(cd) if cd else {}

    # --- Safety helpers ---
    def clamp_command(self, name: str, value: float) -> float:
        """Clamp a value using detected limits or default 0..1."""
        limits = self._limits.get(name)
        if limits:
            lo, hi = limits
            try:
                return float(max(lo, min(hi, value)))
            except Exception:
                return float(value)
        # fallback clamp to [0,1]
        try:
            return 0.0 if value <= 0.0 else (1.0 if value >= 1.0 else float(value))
        except Exception:
            return float(value)

    def _allow_rate(self, name: str) -> bool:
        """Simple rate limiter: allow at most _rate_limit_hz commands per second per control."""
        now = time.time()
        last = self._last_send_ts.get(name)
        if last is None:
            self._last_send_ts[name] = now
            return True
        if now - last < (1.0 / max(1.0, self._rate_limit_hz)):
            return False
        self._last_send_ts[name] = now
        return True

    def _wait_for_ack(self, name: str, expected: float) -> bool:
        """Wait up to _ack_timeout for the controller to reflect the expected value.
        Uses direct index read when possible, falls back to snapshot. Returns True on confirmation.
        """
        start = time.time()
        timer = None
        if RD_ACK_LATENCY is not None:
            timer = RD_ACK_LATENCY.time()
        idx = self.ctrl_index_by_name.get(name)
        while time.time() - start <= self._ack_timeout:
            try:
                if idx is not None:
                    val = float(self.rd.get_current_controller_value(idx))  # type: ignore[attr-defined]
                else:
                    snap = self._snapshot()
                    val = float(snap.get(name, float("nan")))
                # Consider confirmation if value is close enough
                if abs(val - expected) <= 1e-3:
                    if timer is not None:
                        try:
                            timer.observe(time.time() - start)
                        except Exception:
                            # if Histogram.time() returned a context manager, close it
                            try:
                                timer.__exit__(None, None, None)  # type: ignore[attr-defined]
                            except Exception:
                                pass
                    return True
            except Exception:
                # ignore transient read errors and retry until timeout
                pass
            time.sleep(0.01)
        if timer is not None:
            try:
                timer.__exit__(None, None, None)  # type: ignore[attr-defined]
            except Exception:
                pass
        return False

    def _record_retry(self, name: str) -> None:
        self._retry_counts[name] = self._retry_counts.get(name, 0) + 1
        if RD_RETRIES is not None:
            RD_RETRIES.inc()

    def _clear_retries(self, name: str) -> None:
        """Clear retry counter for a given control name (best-effort)."""
        try:
            if name in self._retry_counts:
                # reset to zero (keep key for observability/debugging)
                self._retry_counts[name] = 0
        except Exception:
            pass

    def emergency_stop(self, reason: str = "unknown") -> None:
        """Trigger emergency stop: idempotent and records event."""
        if self._emergency_active:
            return
        self._emergency_active = True
        if RD_EMERGENCY_GAUGE is not None:
            try:
                RD_EMERGENCY_GAUGE.set(1)
            except Exception:
                pass
        try:
            # set maximum brake via any available brake control
            for br in ("TrainBrakeControl", "TrainBrake", "VirtualBrake"):
                idx = self.ctrl_index_by_name.get(br)
                if idx is not None:
                    try:
                        self.rd.set_controller_value(idx, 1.0)  # type: ignore[attr-defined]
                    except Exception:
                        pass
            # persist state to JSON for operator takeover
            try:
                import json

                Path("data").mkdir(parents=True, exist_ok=True)
                # atomic write
                tmp = Path("data") / f"control_status.json.tmp.{int(time.time())}"
                tmp.write_text(
                    json.dumps(
                        {
                            "mode": "manual",
                            "takeover": True,
                            "reason": reason,
                            "ts": time.time(),
                        }
                    ),
                    encoding="utf-8",
                )
                tmp.replace(Path("data") / "control_status.json")
            except Exception:
                pass
            if RD_EMERGENCY is not None:
                RD_EMERGENCY.inc()
        except Exception:
            if RD_ERRORS is not None:
                RD_ERRORS.inc()
        finally:
            # ensure emergency gauge remains set (if metric exists)
            if RD_EMERGENCY_GAUGE is not None:
                try:
                    RD_EMERGENCY_GAUGE.set(1 if self._emergency_active else 0)
                except Exception:
                    pass

    # --- Lecturas puntuales ---
    def read_specials(self) -> Dict[str, Any]:
        # py-raildriver expone helpers; aquí usamos listener snapshot para unificar
        snap = self._snapshot()
        out: Dict[str, Any] = {}
        # LocoName → [Provider, Product, Engine]
        if "!LocoName" in snap:
            loco = snap["!LocoName"] or []
            if isinstance(loco, (list, tuple)) and len(loco) >= 3:
                out.update(
                    {
                        "provider": loco[0],
                        "product": loco[1],
                        "engine": loco[2],
                    }
                )
        # Coordenadas/tiempo/rumbo/pendiente…
        coords = snap.get("!Coordinates")
        if coords and isinstance(coords, (list, tuple)) and len(coords) >= 2:
            out["lat"], out["lon"] = float(coords[0]), float(coords[1])
        else:
            # Fallback directo a RailDriver si el snapshot no trae coordenadas
            try:
                c2 = self.rd.get_current_coordinates()  # type: ignore[attr-defined]
                if isinstance(c2, (list, tuple)) and len(c2) >= 2:
                    out["lat"], out["lon"] = float(c2[0]), float(c2[1])
            except Exception:
                pass
        # Heading en la DLL a veces llega en radianes (~0..6.28). Añade grados también.
        if "!Heading" in snap:
            try:
                hdg = float(snap["!Heading"])
            except Exception:
                hdg = snap["!Heading"]
            out["heading"] = hdg
        elif "heading" not in out:
            try:
                h = float(self.rd.get_current_heading())  # type: ignore[attr-defined]
                out["heading"] = h
            except Exception:
                pass
        if "heading" in out and out["heading"] is not None:
            try:
                _hdg = float(out["heading"])
                if -7.0 <= _hdg <= 7.0:  # parece radianes
                    out["heading_deg"] = (_hdg * 180.0 / 3.141592653589793) % 360.0
                else:
                    out["heading_deg"] = _hdg % 360.0
            except Exception:
                pass
        if "!Gradient" in snap:
            out["gradient"] = snap["!Gradient"]
        elif "gradient" not in out:
            try:
                g = self.rd.get_current_gradient()  # type: ignore[attr-defined]
                out["gradient"] = g
            except Exception:
                pass
        if "!FuelLevel" in snap:
            out["fuel_level"] = snap["!FuelLevel"]
        elif "fuel_level" not in out:
            try:
                f = self.rd.get_current_fuel_level()  # type: ignore[attr-defined]
                out["fuel_level"] = f
            except Exception:
                pass
        if "!IsInTunnel" in snap:
            out["is_in_tunnel"] = bool(snap["!IsInTunnel"])
        elif "is_in_tunnel" not in out:
            try:
                it = self.rd.get_current_is_in_tunnel()  # type: ignore[attr-defined]
                out["is_in_tunnel"] = bool(it)
            except Exception:
                pass
        if "!Time" in snap:
            # !Time suele venir como datetime.time o [h,m,s]
            tval = snap["!Time"]
            if isinstance(tval, (list, tuple)) and len(tval) >= 3:
                out["time_ingame_h"], out["time_ingame_m"], out["time_ingame_s"] = tval[
                    :3
                ]
            else:
                out["time_ingame"] = str(tval)
        else:
            try:
                tobj = self.rd.get_current_time()  # type: ignore[attr-defined]
                out["time_ingame"] = str(tobj)
            except Exception:
                pass
        return out

    def read_controls(self, names: Iterable[str]) -> Dict[str, float]:
        snap = self._snapshot()
        res: Dict[str, float] = {}
        for n in names:
            # Lectura directa preferente por índice
            idx = self.ctrl_index_by_name.get(n)
            if idx is not None:
                try:
                    res[n] = float(self.rd.get_current_controller_value(idx))  # type: ignore[attr-defined]
                    continue
                except Exception:
                    pass
            if n in snap and snap[n] is not None:
                try:
                    res[n] = float(snap[n])
                    continue
                except Exception:
                    pass
            # Fallback: lectura directa (índice es más eficiente)
            idx = self.ctrl_index_by_name.get(n)
            if idx is not None:
                try:
                    res[n] = float(self.rd.get_current_controller_value(idx))  # type: ignore[attr-defined]
                except Exception:
                    # si falla, ignoramos ese control en esta pasada
                    pass
        return res

    # --- RD shim factory with safe set/confirm semantics ---
    def _make_rd(self):
        """Return a thin wrapper around self.rd that implements safe set semantics.

        The wrapper exposes `set_controller_value(name_or_index, value)` when called
        with a name, we canonicalize and find the index; then we send, wait for ack,
        retry up to _max_retries, and escalate to emergency_stop if confirmation fails.
        """

        client = self.rd

        class RDShim:
            def __init__(self, outer: "RDClient"):
                self._outer = outer

            def set_controller_value(self, who, value):
                """Accept either index or name. If name, find index and proceed.
                Implements rate limiting, clamping, ack wait, retries, and metrics.
                """
                outer = self._outer
                # If emergency already active, reject silently
                if getattr(outer, "_emergency_active", False):
                    return

                # Determine index
                if isinstance(who, int):
                    idx: int | None = who
                    name = None
                else:
                    name = str(who)
                    # Allow aliases
                    try:
                        can = name
                        if outer._control_aliases and name in outer._control_aliases:
                            can = outer._control_aliases[name]
                        idx = outer.ctrl_index_by_name.get(can)
                    except Exception:
                        idx = outer.ctrl_index_by_name.get(name)

                # Rate limiting by name if available
                if name and not outer._allow_rate(name):
                    return

                # Clamp value
                try:
                    if name:
                        v = outer.clamp_command(name, float(value))
                    else:
                        v = float(value)
                except Exception:
                    v = float(value)

                # Perform set and confirm with retries
                attempts = 0
                while attempts <= outer._max_retries:
                    attempts += 1
                    try:
                        # If index known, prefer calling driver by index
                        if isinstance(idx, int):
                            client.set_controller_value(idx, v)  # type: ignore[attr-defined]
                        else:
                            # We only support index-based driver calls here; if we don't
                            # have an integer index, escalate to driver error to trigger
                            # retry/emergency logic upstream.
                            raise RuntimeError("no integer controller index available")
                        if RD_SET_CALLS is not None:
                            RD_SET_CALLS.inc()
                    except Exception:
                        outer._record_retry(name or f"idx_{idx}")
                        if RD_ERRORS is not None:
                            RD_ERRORS.inc()
                        # On driver error, try again up to max_retries
                        if attempts > outer._max_retries:
                            outer.emergency_stop("driver_error")
                            return
                        time.sleep(0.05)
                        continue

                    # Wait for ack/confirmation
                    # If ACK watchdog is enabled we enqueue and return optimistically.
                    # The background worker will confirm and escalate if necessary.
                    if getattr(outer, "_ack_watchdog_enabled", False) and name:
                        try:
                            outer._ack_queue.put_nowait((name, v, attempts))
                        except Exception:
                            # If queuing fails, fall back to blocking wait
                            pass
                        # optimistic return: caller assumes set applied
                        if RD_ACKS is not None:
                            try:
                                RD_ACKS.inc()
                            except Exception:
                                pass
                        return

                    ok = False
                    try:
                        if name:
                            ok = outer._wait_for_ack(name, v)
                        elif isinstance(idx, int):
                            # read back by index when name not available
                            try:
                                val = float(client.get_current_controller_value(idx))  # type: ignore[attr-defined]
                                ok = abs(val - v) <= 1e-3
                            except Exception:
                                ok = False
                    except Exception:
                        ok = False

                    if ok:
                        # Clear retries and increment ack metric
                        try:
                            if name:
                                outer._clear_retries(name)
                        except Exception:
                            pass
                        if RD_ACKS is not None:
                            RD_ACKS.inc()
                        return
                    else:
                        outer._record_retry(name or f"idx_{idx}")
                        if attempts > outer._max_retries:
                            outer.emergency_stop("no_ack")
                            return
                        time.sleep(0.02)

        return RDShim(self)

    def stream(self) -> Iterator[Dict[str, Any]]:
        """Genera dicts con specials + subset de controles comunes."""
        common_ctrls = self._common_controls()
        while True:
            row: Dict[str, Any] = self.read_specials()
            row.update(self.read_controls(common_ctrls))
            # Aliases and unified speedometer
            # Throttle alias already handled above; keep single mapping here.
            if "SpeedometerKPH" in row:
                row["Speedometer"] = row["SpeedometerKPH"]
                row["speed_unit"] = "kmh"
            elif "SpeedometerMPH" in row:
                row["Speedometer"] = row["SpeedometerMPH"]
                row["speed_unit"] = "mph"
            # Derivar métricas útiles
            v = row.get("SpeedometerKPH") or row.get("SpeedometerMPH")
            if v is not None:
                if "SpeedometerMPH" in row and "SpeedometerKPH" not in row:
                    v_ms = float(v) * 0.44704
                else:
                    v_ms = float(v) / 3.6
                row["v_ms"], row["v_kmh"] = v_ms, v_ms * 3.6
            # Cacheo de última geo: si falta, usa la última válida
            for k in ("lat", "lon", "heading", "gradient"):
                if row.get(k) is None and self._last_geo.get(k) is not None:
                    row[k] = self._last_geo[k]
            for k in ("lat", "lon", "heading", "gradient"):
                if row.get(k) is not None:
                    self._last_geo[k] = row[k]
            # Alias prácticos para uniformar columnas del CSV
            if "Throttle" not in row and "Regulator" in row:
                row["Throttle"] = row["Regulator"]
            yield row
            time.sleep(self.poll_dt)

    def _common_controls(self) -> List[str]:
        names = set(self.ctrl_index_by_name.keys())
        # prepare normalized map: norm -> original names
        norm_map: Dict[str, List[str]] = {}
        for n in names:
            k = _norm_ctrl_name(n)
            norm_map.setdefault(k, []).append(n)
        # Try to delegate to the centralized controls mapping when available.
        try:
            # local import to avoid cycles
            from profiles import controls as _controls  # type: ignore

            out: List[str] = []
            # First, include any aliases from the canonical mapping that exist on this loco
            for aliases in _controls.CONTROLS.values():
                for a in aliases:
                    if a in names:
                        out.append(a)

            # Also include any names that canonicalize to a known canonical control
            # but may not be listed explicitly in CONTROLS (robustness for variants)
            for n in names:
                try:
                    canon = _controls.canonicalize(n)
                except Exception:
                    canon = None
                if canon is not None:
                    # prefer the original name as present on the driver
                    out.append(n)

            # Additionally, consult suggested_aliases fallback
            suggested = _load_suggested_aliases()
            if suggested:
                for canon, aliases in suggested.items():
                    for a in aliases:
                        if a in names:
                            out.append(a)

            chosen = [n for n in out if n in names]
            if chosen:
                return sorted(set(chosen))
        except Exception:
            # Fall back to the historical heuristic below
            pass

        # Alias / variantes habituales y útiles
        preferred = {
            "SpeedometerKPH",
            "SpeedometerMPH",
            "Regulator",
            "Throttle",
            "TrainBrakeControl",
            "VirtualBrake",
            "TrainBrake",
            "LocoBrakeControl",
            "VirtualEngineBrakeControl",
            "EngineBrake",
            "DynamicBrake",
            "Reverser",
            # Seguridad y sistemas
            "Sifa",
            "SIFA",
            "SifaReset",
            "SifaLight",
            "SifaAlarm",
            "VigilEnable",
            "PZB_85",
            "PZB_70",
            "PZB_55",
            "PZB_1000Hz",
            "PZB_500Hz",
            "PZB_40",
            "PZB_B40",
            "PZB_Warning",
            "AFB",
            "AFB_Speed",
            "LZB_V_SOLL",
            "LZB_V_ZIEL",
            "LZB_DISTANCE",
            # Indicadores útiles
            "BrakePipePressureBAR",
            "TrainBrakeCylinderPressureBAR",
            "Ammeter",
            "ForceBar",
            "BrakeBar",
            # Auxiliares
            "Sander",
            "Headlights",
            "CabLight",
            "DoorsOpenCloseLeft",
            "DoorsOpenCloseRight",
            "VirtualPantographControl",
        }
        # Criterios por patrón para capturar familias comunes
        rx = re.compile(
            r"^(PZB_|Sifa|AFB|LZB_|BrakePipe|TrainBrake|VirtualBrake|VirtualEngineBrake|Headlights|CabLight|Doors)",
            re.I,
        )

        # use normalized matching: if normalized name matches a preferred normalized
        preferred_norms = {_norm_ctrl_name(p) for p in preferred}
        chosen_set = set()
        for n in names:
            if n in preferred or rx.match(n):
                chosen_set.add(n)
                continue
            if _norm_ctrl_name(n) in preferred_norms:
                chosen_set.add(n)
                continue
            # check suggested aliases
            suggested = _load_suggested_aliases()
            if suggested:
                for aliases in suggested.values():
                    if n in aliases:
                        chosen_set.add(n)
                        break

        return sorted(list(chosen_set))

    # -------- Superset de campos para “comprimir” el CSV ----------------------
    def schema(self) -> List[str]:
        base = [
            "provider",
            "product",
            "engine",
            "lat",
            "lon",
            "heading",
            "heading_deg",
            "gradient",
            "fuel_level",
            "is_in_tunnel",
            "time_ingame_h",
            "time_ingame_m",
            "time_ingame_s",
            "time_ingame",
            "v_ms",
            "v_kmh",
            "odom_m",
            "t_wall",
        ]
        return sorted(set(base + self._common_controls()))


# --- TSC actuator shim: expone `rd` con set_brake / set_throttle -------------


def _clamp01(x: float) -> float:
    return 0.0 if x <= 0.0 else (1.0 if x >= 1.0 else float(x))


def _make_rd():
    try:
        client = RDClient(poll_dt=0.2)
    except Exception:
        # Sin RD real disponible -> cae al stub (solo log, no actúa en cabina)
        from runtime.raildriver_stub import rd as _stub  # type: ignore

        return _stub

    # Índices por nombre ya los tienes en RDClient
    idx = client.ctrl_index_by_name

    # Resuelve nombres usando aliases inyectados por pruebas/entorno si están disponibles
    brake_candidates: list[str] | None = None
    throttle_candidates: list[str] | None = None
    injected = getattr(client, "_control_aliases", None)
    if isinstance(injected, dict):
        # esperamos la misma forma que profiles.controls.CONTROLS: canon -> [aliases]
        if "brake" in injected:
            brake_candidates = list(injected.get("brake") or [])
        if "throttle" in injected:
            throttle_candidates = list(injected.get("throttle") or [])

    # Si no hay inyección, o faltan candidatos concretos, intentar el mapping central
    if brake_candidates is None or throttle_candidates is None:
        try:
            from profiles import controls as _controls  # type: ignore

            if brake_candidates is None:
                brake_candidates = _controls.CONTROLS.get("brake", [])
            if throttle_candidates is None:
                throttle_candidates = _controls.CONTROLS.get("throttle", [])
        except Exception:
            # Fallback: listas históricas para compatibilidad
            if brake_candidates is None:
                brake_candidates = [
                    "TrainBrakeControl",
                    "TrainBrake",
                    "VirtualBrake",
                    "LocoBrakeControl",
                    "EngineBrake",
                    "DynamicBrake",
                    "CombinedThrottleBrake",
                    "TrainBrakePipePressure",
                ]
            if throttle_candidates is None:
                throttle_candidates = ["Throttle", "Regulator", "CombinedThrottleBrake"]

    # If still missing, consult suggested aliases with normalization
    suggested = _load_suggested_aliases()
    if suggested:
        if (
            not brake_candidates or len(brake_candidates) == 0
        ) and "brake" in suggested:
            brake_candidates = suggested.get("brake", brake_candidates or [])
        if (
            not throttle_candidates or len(throttle_candidates) == 0
        ) and "throttle" in suggested:
            throttle_candidates = suggested.get("throttle", throttle_candidates or [])

    # Resuelve el primer control que exista para cada función
    # ensure candidates are iterable lists (definitive lists for downstream closures)
    bc: list[str] = list(brake_candidates or [])
    tc: list[str] = list(throttle_candidates or [])
    # assign back to names so inner functions see a concrete list type
    brake_candidates = bc
    throttle_candidates = tc

    brake_idx = next((idx[n] for n in bc if n in idx), None)
    thr_idx = next((idx[n] for n in tc if n in idx), None)

    class RDShim:
        """Interfaz mínima que espera el lazo (solo setters)."""

        def __init__(self, cli: RDClient) -> None:
            self.c = cli

        # El lazo buscará alguno de estos nombres:
        # set_brake / setBrake / setTrainBrake / setCombinedBrake / set_throttle / setThrottle...
        def set_brake(self, v: float) -> None:
            if brake_idx is None:
                # missing control: increment metric if available
                if RD_MISSING is not None:
                    RD_MISSING.inc()
                return
            name = next((n for n in bc if n in self.c.ctrl_index_by_name), None)
            # rate limit (use fallback if client missing helper)
            allow_rate_fn = getattr(self.c, "_allow_rate", None)
            use_rate = allow_rate_fn is not None and hasattr(self.c, "_last_send_ts")
            if name and use_rate and callable(allow_rate_fn):
                try:
                    if not allow_rate_fn(name):
                        try:
                            self.c.logger.debug("rate-limited brake command %s", name)
                        except Exception:
                            pass
                        return
                except Exception:
                    # If the client method exists but is misconfigured, don't block commands
                    pass
            try:
                if RD_SET_CALLS is not None:
                    RD_SET_CALLS.inc()
                # Use client clamp_command only if the client has initialized runtime state
                if hasattr(self.c, "_limits") and hasattr(self.c, "clamp_command"):
                    clamp_fn = getattr(self.c, "clamp_command")
                else:

                    def _fallback_clamp(n, x):
                        return _clamp01(x)

                    clamp_fn = _fallback_clamp
                val = clamp_fn(name or "VirtualBrake", v)
                self.c.rd.set_controller_value(brake_idx, float(val))  # type: ignore[attr-defined]
                # optimistic ack accounting (real ack detection not implemented)
                if RD_ACKS is not None:
                    RD_ACKS.inc()
            except Exception:
                if RD_ERRORS is not None:
                    RD_ERRORS.inc()
                # record retry and possibly escalate (use fallbacks)
                # only call record_retry when the client initialized retry state
                if hasattr(self.c, "_retry_counts") and hasattr(
                    self.c, "_record_retry"
                ):
                    record_retry = getattr(self.c, "_record_retry")
                else:

                    def _fallback_record(n):
                        return None

                    record_retry = _fallback_record
                record_retry(name or "brake")
                retry_counts = getattr(self.c, "_retry_counts", {})
                max_retries = getattr(self.c, "_max_retries", 3)
                if retry_counts.get(name or "brake", 0) > max_retries:
                    try:
                        self.c.logger.error(
                            "max retries exceeded for brake %s -> emergency", name
                        )
                    except Exception:
                        pass
                    emergency_fn = getattr(self.c, "emergency_stop", lambda r: None)
                    try:
                        emergency_fn("max_retries_brake")
                    except Exception:
                        pass
                pass

        def setThrottle(self, v: float) -> None:  # alias
            self.set_throttle(v)

        def set_throttle(self, v: float) -> None:
            if thr_idx is None:
                if RD_MISSING is not None:
                    RD_MISSING.inc()
                return
            name = next((n for n in tc if n in self.c.ctrl_index_by_name), None)
            allow_rate_fn = getattr(self.c, "_allow_rate", None)
            use_rate = allow_rate_fn is not None and hasattr(self.c, "_last_send_ts")
            if name and use_rate and callable(allow_rate_fn):
                try:
                    if not allow_rate_fn(name):
                        try:
                            self.c.logger.debug(
                                "rate-limited throttle command %s", name
                            )
                        except Exception:
                            pass
                        return
                except Exception:
                    # If the client method exists but is misconfigured, don't block commands
                    pass
            try:
                if RD_SET_CALLS is not None:
                    RD_SET_CALLS.inc()
                if hasattr(self.c, "_limits") and hasattr(self.c, "clamp_command"):
                    clamp_fn = getattr(self.c, "clamp_command")
                else:

                    def _fallback_clamp(n, x):
                        return _clamp01(x)

                    clamp_fn = _fallback_clamp
                val = clamp_fn(name or "Throttle", v)
                self.c.rd.set_controller_value(thr_idx, float(val))  # type: ignore[attr-defined]
                if RD_ACKS is not None:
                    RD_ACKS.inc()
            except Exception:
                if RD_ERRORS is not None:
                    RD_ERRORS.inc()
                if hasattr(self.c, "_retry_counts") and hasattr(
                    self.c, "_record_retry"
                ):
                    record_retry = getattr(self.c, "_record_retry")
                else:

                    def _fallback_record(n):
                        return None

                    record_retry = _fallback_record
                record_retry(name or "throttle")
                retry_counts = getattr(self.c, "_retry_counts", {})
                max_retries = getattr(self.c, "_max_retries", 3)
                if retry_counts.get(name or "throttle", 0) > max_retries:
                    try:
                        self.c.logger.error(
                            "max retries exceeded for throttle %s -> emergency", name
                        )
                    except Exception:
                        pass
                    emergency_fn = getattr(self.c, "emergency_stop", lambda r: None)
                    try:
                        emergency_fn("max_retries_throttle")
                    except Exception:
                        pass
                pass

    return RDShim(client)


# `rd` es lo que importa para runtime.actuators.send_to_rd(...)
rd = _make_rd()
