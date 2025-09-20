from __future__ import annotations

import os
import sys
import time
from typing import Any, Dict, Iterable, Iterator, List
import platform
import struct
from pathlib import Path
import re
import logging

# Optional Prometheus metrics (do not hard-fail if library missing)
try:
    from prometheus_client import Counter  # type: ignore

    RD_SET_CALLS = Counter("trainsim_rd_set_calls_total", "Number of RD set calls")
    RD_ERRORS = Counter("trainsim_rd_errors_total", "Number of RD errors")
    RD_MISSING = Counter("trainsim_rd_missing_control_total", "Number of attempts to set missing controls")
except Exception:
    RD_SET_CALLS = None  # type: ignore
    RD_ERRORS = None  # type: ignore
    RD_MISSING = None  # type: ignore


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
    from ingestion.rd_fake import FakeRailDriver as RailDriver  # type: ignore  # noqa: E402, F811
    from ingestion.rd_fake import FakeListener as Listener  # type: ignore  # noqa: E402, F811


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
        raise FileNotFoundError(f"No se encontró {want.name} en {base}. Define RAILWORKS_PLUGINS o TSC_RD_DLL_DIR.")
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
    rd: "RailDriver"
    listener: "Listener"
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
        control_aliases: dict | None = None,
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
                    self.logger.debug(
                        "using RailDriver DLL: %s", dll_path
                    )
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
        try:
            self.rd.set_rail_driver_connected(True)  # type: ignore[attr-defined]
        except Exception:
            # Versiones antiguas ignoran el parámetro; continuamos.
            pass

        # Índices cacheados por nombre para lecturas directas cuando conviene
        self.ctrl_index_by_name: Dict[str, int] = {
            name: idx
            for idx, name in self.rd.get_controller_list()  # type: ignore[attr-defined]
        }

        # Listener para cambios y snapshots unificados
        self.listener = Listener(self.rd, interval=self.poll_dt)  # type: ignore[call-arg]
        # Caché de la última geo conocida para rellenar huecos momentáneos
        self._last_geo: Dict[str, Any] = {
            "lat": None,
            "lon": None,
            "heading": None,
            "gradient": None,
        }
        # Suscribir todos los controles disponibles (las especiales se evalúan siempre)
        try:
            self.listener.subscribe(list(self.ctrl_index_by_name.keys()))  # type: ignore[attr-defined]
        except Exception:
            # Si cambia de locomotora y hay controles ausentes, se puede re-suscribir más tarde
            pass

    # --- Lectura mediante iteración única del listener ---
    def _snapshot(self) -> Dict[str, Any]:
        """Fuerza una iteración del listener y devuelve una copia del estado actual."""
        # No arrancamos hilo; usamos una iteración síncrona
        self.listener._main_iteration()  # type: ignore[attr-defined]
        cd = getattr(self.listener, "current_data", None)
        return dict(cd) if cd else {}

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
                out["time_ingame_h"], out["time_ingame_m"], out["time_ingame_s"] = tval[:3]
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

    def stream(self) -> Iterator[Dict[str, Any]]:
        """Genera dicts con specials + subset de controles comunes."""
        common_ctrls = self._common_controls()
        while True:
            row: Dict[str, Any] = self.read_specials()
            row.update(self.read_controls(common_ctrls))
            # Aliases and unified speedometer
            if "Throttle" not in row and "Regulator" in row:
                row["Throttle"] = row["Regulator"]
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
        # Try to delegate to the centralized controls mapping when available.
        try:
            # local import to avoid cycles
            from profiles import controls as _controls  # type: ignore

            out: List[str] = []
            for aliases in _controls.CONTROLS.values():
                out.extend(aliases)
            # Keep only aliases present in this locomotive's controller list
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
        chosen = {n for n in names if (n in preferred or rx.match(n))}
        return sorted(chosen)

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
    brake_candidates = None
    throttle_candidates = None
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

    # Resuelve el primer control que exista para cada función
    brake_idx = next((idx[n] for n in brake_candidates if n in idx), None)
    thr_idx = next((idx[n] for n in throttle_candidates if n in idx), None)

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
            try:
                if RD_SET_CALLS is not None:
                    RD_SET_CALLS.inc()
                self.c.rd.set_controller_value(brake_idx, _clamp01(v))  # type: ignore[attr-defined]
            except Exception:
                if RD_ERRORS is not None:
                    RD_ERRORS.inc()
                pass

        def setThrottle(self, v: float) -> None:  # alias
            self.set_throttle(v)

        def set_throttle(self, v: float) -> None:
            if thr_idx is None:
                if RD_MISSING is not None:
                    RD_MISSING.inc()
                return
            try:
                if RD_SET_CALLS is not None:
                    RD_SET_CALLS.inc()
                self.c.rd.set_controller_value(thr_idx, _clamp01(v))  # type: ignore[attr-defined]
            except Exception:
                if RD_ERRORS is not None:
                    RD_ERRORS.inc()
                pass

    return RDShim(client)


# `rd` es lo que importa para runtime.actuators.send_to_rd(...)
rd = _make_rd()
