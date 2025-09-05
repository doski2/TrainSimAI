from __future__ import annotations

import os
import sys
import time
from typing import Any, Dict, Iterable, Iterator, List
import platform
from pathlib import Path
import re


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
from raildriver import RailDriver  # noqa: E402
from raildriver.events import Listener  # type: ignore  # noqa: E402


# Claves especiales disponibles en Listener (no se suscriben; se evalúan siempre)
SPECIAL_KEYS: List[str] = list(Listener.special_fields.keys())  # type: ignore[attr-defined]


def _locate_raildriver_dll() -> str | None:
    """Selecciona la DLL que coincide con la arquitectura de Python.

    - En Python de 64 bits, preferir 'RailDriver64.dll'.
    - En Python de 32 bits, preferir 'RailDriver.dll'.
    - Busca rutas típicas de Steam; permitir sobreescritura via env RAILWORKS_PLUGINS.
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
        / "Steam" / "steamapps" / "common" / "RailWorks" / "plugins",
        Path(os.environ.get("PROGRAMFILES", r"C:\\Program Files"))
        / "Steam" / "steamapps" / "common" / "RailWorks" / "plugins",
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


class RDClient:
    """
    Wrapper de py-raildriver con utilidades de lectura puntual y streaming.

    - Usa `Listener` para obtener snapshot consistente de controles + especiales.
    - Expone utilidades para obtener un subconjunto habitual de controles.
    """

    def __init__(self, poll_dt: float = 0.2, poll_hz: float | None = None) -> None:
        if poll_hz and poll_hz > 0:
            self.poll_dt = 1.0 / float(poll_hz)
        else:
            self.poll_dt = float(poll_dt)
        # Seleccionar la DLL adecuada para evitar WinError 193 (arquitecturas distintas)
        dll_path = _locate_raildriver_dll()
        self.rd = RailDriver(dll_location=dll_path) if dll_path else RailDriver()
        # Necesario para intercambiar datos con TS
        try:
            self.rd.set_rail_driver_connected(True)
        except Exception:
            # Versiones antiguas ignoran el parámetro; continúamos.
            pass

        # Índices cacheados por nombre para lecturas directas cuando conviene
        self.ctrl_index_by_name: Dict[str, int] = {
            name: idx for idx, name in self.rd.get_controller_list()
        }

        # Listener para cambios y snapshots unificados
        self.listener = Listener(self.rd, interval=self.poll_dt)
        # Suscribir todos los controles disponibles (las especiales se evalúan siempre)
        try:
            self.listener.subscribe(list(self.ctrl_index_by_name.keys()))
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
        # py‑raildriver expone helpers; aquí usamos listener snapshot para unificar
        snap = self._snapshot()
        out: Dict[str, Any] = {}
        # LocoName → [Provider, Product, Engine]
        if "!LocoName" in snap:
            loco = snap["!LocoName"] or []
            if isinstance(loco, (list, tuple)) and len(loco) >= 3:
                out.update({
                    "provider": loco[0],
                    "product": loco[1],
                    "engine": loco[2],
                })
        # Coordenadas/tiempo/rumbo/pendiente…
        coords = snap.get("!Coordinates")
        if coords and isinstance(coords, (list, tuple)) and len(coords) >= 2:
            out["lat"], out["lon"] = coords[0], coords[1]
        if "!Heading" in snap:
            out["heading"] = snap["!Heading"]
        if "!Gradient" in snap:
            out["gradient"] = snap["!Gradient"]
        if "!FuelLevel" in snap:
            out["fuel_level"] = snap["!FuelLevel"]
        if "!IsInTunnel" in snap:
            out["is_in_tunnel"] = bool(snap["!IsInTunnel"])
        if "!Time" in snap:
            # !Time suele venir como datetime.time o [h,m,s]
            tval = snap["!Time"]
            if isinstance(tval, (list, tuple)) and len(tval) >= 3:
                out["time_ingame_h"], out["time_ingame_m"], out["time_ingame_s"] = tval[:3]
            else:
                out["time_ingame"] = str(tval)
        return out

    def read_controls(self, names: Iterable[str]) -> Dict[str, float]:
        snap = self._snapshot()
        res: Dict[str, float] = {}
        for n in names:
            if n in snap and snap[n] is not None:
                try:
                    res[n] = float(snap[n])
                    continue
                except Exception:
                    pass
            # fallback lectura directa (índice es más eficiente)
            idx = self.ctrl_index_by_name.get(n)
            if idx is not None:
                try:
                    res[n] = float(self.rd.get_current_controller_value(idx))
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
            # Derivar métricas útiles
            v = row.get("SpeedometerKPH") or row.get("SpeedometerMPH")
            if v is not None:
                if "SpeedometerMPH" in row and "SpeedometerKPH" not in row:
                    v_ms = float(v) * 0.44704
                else:
                    v_ms = float(v) / 3.6
                row["v_ms"], row["v_kmh"] = v_ms, v_ms * 3.6
            yield row
            time.sleep(self.poll_dt)

    def _common_controls(self) -> Iterable[str]:
        names = set(self.ctrl_index_by_name.keys())
        # Alias / variantes habituales y útiles
        preferred = {
            "SpeedometerKPH", "SpeedometerMPH",
            "Regulator", "Throttle",
            "TrainBrakeControl", "VirtualBrake", "TrainBrake",
            "LocoBrakeControl", "VirtualEngineBrakeControl", "EngineBrake",
            "DynamicBrake", "Reverser",
            # Seguridad y sistemas
            "Sifa", "SIFA", "SifaReset", "SifaLight", "SifaAlarm", "VigilEnable",
            "PZB_85", "PZB_70", "PZB_55", "PZB_1000Hz", "PZB_500Hz", "PZB_40", "PZB_B40", "PZB_Warning",
            "AFB", "AFB_Speed", "LZB_V_SOLL", "LZB_V_ZIEL", "LZB_DISTANCE",
            # Indicadores útiles
            "BrakePipePressureBAR", "TrainBrakeCylinderPressureBAR", "Ammeter", "ForceBar", "BrakeBar",
            # Auxiliares
            "Sander", "Headlights", "CabLight", "DoorsOpenCloseLeft", "DoorsOpenCloseRight", "VirtualPantographControl",
        }
        # Criterios por patrón para capturar familias comunes
        rx = re.compile(r"^(PZB_|Sifa|AFB|LZB_|BrakePipe|TrainBrake|VirtualBrake|VirtualEngineBrake|Headlights|CabLight|Doors)", re.I)
        chosen = {n for n in names if (n in preferred or rx.match(n))}
        return sorted(chosen)
