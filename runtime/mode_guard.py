from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ModeGuard:
    mode: str  # "full", "brake", "advisory"

    @property
    def send_throttle(self) -> bool:
        return self.mode == "full"

    @property
    def send_brake(self) -> bool:
        return self.mode in ("full", "brake")

    def clamp_outputs(self, throttle_cmd, brake_cmd):
        """
        Devuelve la tupla (throttle_to_send, brake_to_send) teniendo en cuenta el modo.
        - full:     envía ambos
        - brake:    solo freno (no toca tu acelerador)
        - advisory: no envía nada (solo consejo/logs)
        """
        t = throttle_cmd if self.send_throttle else None
        b = brake_cmd if self.send_brake else None
        return t, b
