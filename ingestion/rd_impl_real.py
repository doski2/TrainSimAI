"""
Adaptador RD real para TrainSimAI (plantilla mínima).

Uso:
  TSC_RD_IMPL=ingestion.rd_impl_real:rd_impl

Contrato:
  - Exponer 'rd_impl' (función) que devuelve un objeto con:
      apply(throttle: float, brake: float) -> tuple[float,float]
      close() -> None (opcional)

Backends:
  - Si está disponible 'raildriver' (pip), actuará sobre Regulator/TrainBrakeControl.
  - Si no, funcionará como no-op (solo validará import y podrás ver el nombre del método en rd_send.log).
"""

from __future__ import annotations

# Nombres de controles (ajústalos si tu RD usa otros)
CONTROL_NAMES = {
    "throttle": "Regulator",
    "brake": "TrainBrakeControl",
}

try:
    # pip install raildriver
    from raildriver.client import RailDriver  # type: ignore
except Exception:
    RailDriver = None  # sin dependencia, seguimos como no-op


def _clamp01(x: float) -> float:
    try:
        v = float(x)
    except Exception:
        v = 0.0
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


class RDAdapter:
    def __init__(self) -> None:
        self._rd = None
        if RailDriver is not None:
            try:
                self._rd = RailDriver()
            except Exception:
                self._rd = None  # seguimos en no-op

    def apply(self, throttle: float, brake: float):
        """Aplica mandos (0..1). Devuelve (t_aplicado, b_aplicado)."""
        t = _clamp01(throttle)
        b = _clamp01(brake)
        if self._rd is not None:
            try:
                self._rd.set_controller_value(CONTROL_NAMES["throttle"], t)
                self._rd.set_controller_value(CONTROL_NAMES["brake"], b)
            except Exception:
                # si falla, no reventamos el loop; queda en no-op
                pass
        return t, b

    def close(self) -> None:
        # Si tu backend necesita liberar recursos, hazlo aquí
        pass


def rd_impl() -> RDAdapter:
    """Fábrica esperada por el runtime."""
    return RDAdapter()
