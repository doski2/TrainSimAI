"""
Adaptador RD real para TrainSimAI (plantilla robusta y minimalista).

Uso (entorno):
  TSC_RD_IMPL=ingestion.rd_impl_real:rd_impl
Opcionales:
  TSC_RD_THROTTLE_NAME=Regulator            (override del nombre)
  TSC_RD_BRAKE_NAME=TrainBrakeControl
  TSC_RD_INVERT_THROTTLE=0|1
  TSC_RD_INVERT_BRAKE=0|1
  TSC_RD_SCALE_01=0|1                       (si tu backend NO usa 0..1)
  TSC_RD_EPS=0.01                           (umbral de cambio para escribir)

Contrato:
  - Exponer 'rd_impl()' → objeto con .apply(throttle, brake) -> tuple[float,float]
  - .close() opcional
Backend:
  - Si existe 'raildriver' (pip), escribe en {Regulator, TrainBrakeControl} o en los
    nombres que indiques por entorno. Si no hay raildriver, se queda en no-op.
"""

from __future__ import annotations
from typing import Tuple, Dict, Optional, Any
import os

# Nombres por defecto (puedes sobreescribirlos por entorno)
DEFAULT_CONTROL_NAMES: Dict[str, str] = {
    "throttle": "Regulator",
    "brake": "TrainBrakeControl",
}

try:
    # pip install raildriver
    from raildriver.client import RailDriver  # type: ignore
except Exception:
    RailDriver = None


def _clamp01(x: float) -> float:
    try:
        v = float(x)
    except Exception:
        v = 0.0
    return 0.0 if v < 0.0 else 1.0 if v > 1.0 else v


class RDAdapter:
    def __init__(self) -> None:
        # Backend
        self._rd: Any = None
        if RailDriver is not None:
            try:
                self._rd = RailDriver()
            except Exception:
                self._rd = None  # seguimos en no-op

        # Config desde entorno
        self._names: Dict[str, str] = {
            "throttle": os.environ.get("TSC_RD_THROTTLE_NAME", DEFAULT_CONTROL_NAMES["throttle"]),
            "brake": os.environ.get("TSC_RD_BRAKE_NAME", DEFAULT_CONTROL_NAMES["brake"]),
        }
        self._invert_throttle = os.environ.get("TSC_RD_INVERT_THROTTLE", "0") == "1"
        self._invert_brake = os.environ.get("TSC_RD_INVERT_BRAKE", "0") == "1"
        self._scale_01 = os.environ.get("TSC_RD_SCALE_01", "1") == "1"  # por defecto 0..1
        try:
            self._eps = float(os.environ.get("TSC_RD_EPS", "0.01"))
        except Exception:
            self._eps = 0.01

        # Últimos valores escritos (anti-ruido)
        self._last: Dict[str, Optional[float]] = {"throttle": None, "brake": None}

    def apply(self, throttle: float, brake: float) -> Tuple[float, float]:
        """
        Aplica mandos (0..1). Devuelve (t_aplicado, b_aplicado).
        Si no hay backend, hace no-op (pero valida el contrato).
        """
        t = _clamp01(throttle)
        b = _clamp01(brake)

        # inversores
        if self._invert_throttle:
            t = 1.0 - t
        if self._invert_brake:
            b = 1.0 - b

        # escala (si algún backend esperara -1..1 u otra convención, aquí lo adaptarías)
        if not self._scale_01:
            # ejemplo: pasar 0..1 a -1..1
            t = (t * 2.0) - 1.0
            b = (b * 2.0) - 1.0

        if self._rd is not None:
            try:
                # Anti-ruido: solo escribir si cambia lo suficiente
                lt: Optional[float] = self._last["throttle"]
                lb: Optional[float] = self._last["brake"]
                if lt is None or abs(t - lt) >= self._eps:
                    self._rd.set_controller_value(self._names["throttle"], t)
                    self._last["throttle"] = t
                if lb is None or abs(b - lb) >= self._eps:
                    self._rd.set_controller_value(self._names["brake"], b)
                    self._last["brake"] = b
            except Exception:
                # no reventamos el loop; queda en no-op si falla set_controller_value
                pass
        return t, b

    def close(self) -> None:
        # Si tu backend necesita liberar recursos, hazlo aquí
        try:
            if self._rd is not None and hasattr(self._rd, "close"):
                self._rd.close()
        except Exception:
            pass


def rd_impl() -> RDAdapter:
    """Fábrica esperada por el runtime."""
    return RDAdapter()

