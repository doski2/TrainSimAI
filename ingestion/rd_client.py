from __future__ import annotations

import os
import sys
import time
from typing import Any, Dict, Iterable, List


def _ensure_raildriver_on_path() -> None:
    """
    Añade el paquete local `py-raildriver-master` al sys.path si existe
    junto al repo, para poder `import raildriver` sin instalación previa.
    """
    here = os.path.abspath(os.path.dirname(__file__))
    repo_root = os.path.abspath(os.path.join(here, os.pardir))
    candidate = os.path.join(repo_root, "py-raildriver-master")
    if os.path.isdir(candidate) and candidate not in sys.path:
        sys.path.insert(0, candidate)


_ensure_raildriver_on_path()

# Importa RailDriver y Listener del paquete local
from raildriver.library import RailDriver  # type: ignore  # noqa: E402
from raildriver.events import Listener  # type: ignore  # noqa: E402


# Claves especiales disponibles en Listener (no se suscriben; se evalúan siempre)
SPECIAL_KEYS: List[str] = list(Listener.special_fields.keys())  # type: ignore[attr-defined]


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
        self.rd = RailDriver()
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
        return dict(self.listener.current_data)

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

    def stream(self) -> Iterable[Dict[str, Any]]:
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
        prefer = [
            "SpeedometerKPH", "SpeedometerMPH",
            "Regulator", "Throttle",
            "TrainBrakeControl", "LocoBrakeControl",
            "DynamicBrake", "Reverser",
            # seguridad (si existen)
            "SIFA", "VigilEnable", "PZB_85", "PZB_70", "PZB_55",
            "PZB_1000", "PZB_500", "PZB_40",
            "AFB_Speed", "LZB_V_SOLL", "LZB_V_ZIEL", "LZB_DISTANCE",
        ]
        return [n for n in prefer if n in names]
