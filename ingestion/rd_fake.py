from __future__ import annotations

import datetime as _dt
import math
import time
from typing import Any, Dict, Iterable, List, Tuple


class FakeRailDriver:
    """
    Simulador ligero compatible con la API de `raildriver.library.RailDriver`.

    - Implementa los getters usados por Listener: coordenadas, heading, gradiente,
      fuel, is_in_tunnel, time y loco_name.
    - Implementa lectura por índice o por nombre para `get_current_controller_value`.
    - Física muy simple: v' = a(throttle, brake) - rozamiento; integra posición en
      torno a un punto en Dresde.
    """

    def __init__(self) -> None:
        # Estado de conexión (para compatibilidad con set_rail_driver_connected)
        self._sim_connected = False

        # Reloj y física
        self._t_wall0 = time.time()
        self._last_t = self._t_wall0
        self._lat = 51.1135139465332
        self._lon = 13.609774589538574
        # Heading en radianes (~116.6°)
        self._heading = 2.034233331680298
        self._gradient = 0.0
        self._fuel = 0.0
        self._is_tunnel = False
        # Hora in-game (h, m, s) base; acumulador en segundos
        self._t_ingame_sec = float(18 * 3600 + 6 * 60 + 2)
        self._v_ms = 0.0

        # Definición de controles y rangos
        names = [
            "SpeedometerKPH",
            "Regulator",
            "VirtualBrake",
            "VirtualEngineBrakeControl",
            "Reverser",
            "BrakePipePressureBAR",
            "TrainBrakeCylinderPressureBAR",
            "AFB",
            "AFB_Speed",
        ]
        self._controls_order: List[Tuple[int, str]] = list(enumerate(names))
        self._idx_by_name: Dict[str, int] = {n: i for i, n in self._controls_order}

        self._minmax: Dict[str, Tuple[float, float]] = {
            "SpeedometerKPH": (0.0, 180.0),
            "Regulator": (0.0, 1.0),
            "VirtualBrake": (0.0, 1.0),
            "VirtualEngineBrakeControl": (-1.0, 1.0),
            "Reverser": (-1.0, 1.0),
            "BrakePipePressureBAR": (0.0, 5.0),
            "TrainBrakeCylinderPressureBAR": (0.0, 10.0),
            "AFB": (0.0, 1.0),
            "AFB_Speed": (0.0, 180.0),
        }
        self._values: Dict[str, float] = {
            "SpeedometerKPH": 0.0,
            "Regulator": 0.0,
            "VirtualBrake": 0.0,
            "VirtualEngineBrakeControl": 0.0,
            "Reverser": 1.0,
            "BrakePipePressureBAR": 5.0,
            "TrainBrakeCylinderPressureBAR": 0.0,
            "AFB": 0.0,
            "AFB_Speed": 0.0,
        }

    # --- Compatibilidad API raildriver ---
    def __repr__(self) -> str:
        return "ingestion.rd_fake.FakeRailDriver"

    def set_rail_driver_connected(self, value: bool) -> None:
        self._sim_connected = bool(value)

    def get_controller_list(self) -> Iterable[Tuple[int, str]]:
        return list(self._controls_order)

    def get_controller_index(self, name: str) -> int:
        if name not in self._idx_by_name:
            raise ValueError(f"Controller index not found for {name}")
        return self._idx_by_name[name]

    def get_min_controller_value(self, index_or_name: int | str) -> float:
        name = self._name_from_index_or_name(index_or_name)
        return self._minmax.get(name, (0.0, 1.0))[0]

    def get_max_controller_value(self, index_or_name: int | str) -> float:
        name = self._name_from_index_or_name(index_or_name)
        return self._minmax.get(name, (0.0, 1.0))[1]

    def get_current_controller_value(self, index_or_name: int | str) -> float:
        self._step()
        name = self._name_from_index_or_name(index_or_name)
        if name == "SpeedometerKPH":
            return float(self._v_ms * 3.6)
        return float(self._values.get(name, 0.0))

    def set_controller_value(self, index_or_name: int | str, value: float) -> None:
        name = self._name_from_index_or_name(index_or_name)
        vmin, vmax = self._minmax.get(name, (0.0, 1.0))
        self._values[name] = float(max(vmin, min(vmax, value)))

    # --- Specials usados por Listener ---
    def get_current_coordinates(self) -> Tuple[float, float]:
        self._step()
        return (self._lat, self._lon)

    def get_current_heading(self) -> float:
        self._step()
        return float(self._heading)

    def get_current_gradient(self) -> float:
        return float(self._gradient)

    def get_current_fuel_level(self) -> float:
        return float(self._fuel)

    def get_current_is_in_tunnel(self) -> bool:
        return bool(self._is_tunnel)

    def get_current_time(self):
        # Devuelve datetime.time para ser compatible con py-raildriver
        t = int(self._t_ingame_sec) % 86400
        h = t // 3600
        m = (t % 3600) // 60
        s = t % 60
        return _dt.time(hour=h, minute=m, second=s)

    def get_loco_name(self):
        return ["DTG", "Dresden", "DB BR146.0"]

    # --- Utilidades internas ---
    def _name_from_index_or_name(self, index_or_name: int | str) -> str:
        if isinstance(index_or_name, int):
            for idx, nm in self._controls_order:
                if idx == index_or_name:
                    return nm
            raise ValueError(f"Invalid controller index: {index_or_name}")
        else:
            if index_or_name not in self._idx_by_name:
                raise ValueError(f"Controller index not found for {index_or_name}")
            return index_or_name

    def _step(self) -> None:
        # Integración de física y reloj en tiempo de pared
        t = time.time()
        dt = max(0.0, t - self._last_t)
        self._last_t = t
        # Reloj in-game avanza 1:1 con el tiempo real
        self._t_ingame_sec = (self._t_ingame_sec + dt) % 86400.0

        thr = float(self._values.get("Regulator", 0.0))
        brk = float(self._values.get("VirtualBrake", 0.0))
        # Aceleración: empuje - freno - rozamiento proporcional
        a = 0.8 * thr - 1.2 * brk - 0.05 * self._v_ms
        self._v_ms = max(0.0, self._v_ms + a * dt)

        # Actualiza manómetros de forma plausible
        self._values["TrainBrakeCylinderPressureBAR"] = max(0.0, min(10.0, 10.0 * brk))
        self._values["BrakePipePressureBAR"] = max(0.0, 5.0 - 4.0 * brk)

        # Integra posición (aprox.): 1° lat ≈ 111_320 m; 1° lon ≈ 111_320 * cos(lat)
        if self._v_ms > 0.0:
            dl = self._v_ms * dt
            m_per_deg_lat = 111_320.0
            m_per_deg_lon = m_per_deg_lat * math.cos(math.radians(self._lat))
            dx = dl * math.cos(self._heading)
            dy = dl * math.sin(self._heading)
            self._lat += dy / m_per_deg_lat
            self._lon += dx / m_per_deg_lon


# Nota: Usaremos el Listener real de py-raildriver. Este fake no define Listener
# porque `raildriver.events.Listener` ya funciona si el RailDriver implementa
# la firma esperada (lectura por nombre y specials), como aquí.


# Listener simulado compatible con la API de raildriver.events.Listener
class FakeListener:
    """
    Implementa la misma interfaz esencial que `raildriver.events.Listener`:
    - atributos: `current_data`, `previous_data`, `subscribed_fields`, `interval`
    - métodos: `subscribe(field_names)`, `_main_iteration()`
    - `special_fields`: mapping de claves especiales a métodos del driver
    """

    special_fields: Dict[str, str] = {
        '!Coordinates': 'get_current_coordinates',
        '!FuelLevel': 'get_current_fuel_level',
        '!Gradient': 'get_current_gradient',
        '!Heading': 'get_current_heading',
        '!IsInTunnel': 'get_current_is_in_tunnel',
        '!LocoName': 'get_loco_name',
        '!Time': 'get_current_time',
    }

    def __init__(self, raildriver: Any, interval: float = 0.5) -> None:
        import collections
        self.interval = float(interval)
        self.raildriver = raildriver
        self.current_data = collections.defaultdict(lambda: None)
        self.previous_data = collections.defaultdict(lambda: None)
        self.subscribed_fields: List[str] = []
        self.iteration = 0

    def subscribe(self, field_names: List[str]) -> None:
        available = {name for _, name in self.raildriver.get_controller_list()}
        for f in field_names:
            if f not in available:
                raise ValueError(f"Cannot subscribe to a missing controller {f}")
        self.subscribed_fields = list(field_names)

    def _main_iteration(self) -> None:
        import copy
        self.iteration += 1
        self.previous_data = copy.copy(self.current_data)
        # Controles
        for name in self.subscribed_fields:
            try:
                val = self.raildriver.get_current_controller_value(name)
            except Exception:
                # elimina si desaparece (cambio de loco, etc.)
                try:
                    del self.current_data[name]
                except Exception:
                    pass
            else:
                self.current_data[name] = val
        # Especiales
        for field_name, method_name in self.special_fields.items():
            try:
                self.current_data[field_name] = getattr(self.raildriver, method_name)()
            except Exception:
                # si falla, deja el valor previo o None
                self.current_data[field_name] = self.current_data.get(field_name)

