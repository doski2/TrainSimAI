from __future__ import annotations

from dataclasses import dataclass

"""Guardas y utilidades para el control online."""


def clamp01(x: float) -> float:
    return 1.0 if x > 1.0 else 0.0 if x < 0.0 else x


@dataclass
class RateLimiter:
    max_delta_per_s: float = 0.7  # cambio máximo absoluto por segundo
    _last: float = 0.0

    def reset(self, value: float = 0.0) -> None:
        self._last = clamp01(float(value))

    def step(self, desired: float, dt: float) -> float:
        desired = clamp01(float(desired))
        dmax = max(1e-6, float(self.max_delta_per_s)) * max(1e-3, float(dt))
        lo, hi = self._last - dmax, self._last + dmax
        out = min(hi, max(lo, desired))
        self._last = out
        return out


def overspeed_guard(
    speed_kph: float, limit_kph: float | None, *, delta_kph: float = 0.5
) -> float:
    """Devuelve nivel mínimo de freno [0..1] cuando se excede el límite en delta_kph."""
    if limit_kph is None:
        return 0.0
    if speed_kph <= limit_kph + delta_kph:
        return 0.0
    # excesos mayores → más freno (rampa suave)
    exc = speed_kph - (limit_kph + delta_kph)
    # Rampa más agresiva: suelo 0.2 y +0.1 por cada 1 km/h extra
    return clamp01(0.2 + 0.1 * exc)


class JerkBrakeLimiter:
    """
    Limitador de jerk para el freno (dos etapas):
      - Limita la **tasa** de cambio del freno (max_rate_per_s).
      - Limita la **variación de la tasa** (jerk: max_jerk_per_s2).
    Integra internamente la salida.
    """

    def __init__(self, max_rate_per_s: float = 1.8, max_jerk_per_s2: float = 6.0):
        self.max_rate = float(max_rate_per_s)
        self.max_jerk = float(max_jerk_per_s2)
        self._rate = 0.0
        self._y = 0.0

    def reset(self, y0: float = 0.0):
        self._y = clamp01(float(y0))
        self._rate = 0.0

    def step(self, target: float, dt: float) -> float:
        # Tasa deseada para alcanzar target en un dt (cap a max_rate)
        r_target = (target - self._y) / dt
        r_target = max(-self.max_rate, min(self.max_rate, r_target))
        # Limitar jerk (cambio de tasa)
        dr = r_target - self._rate
        max_dr = self.max_jerk * dt
        if dr > max_dr:
            dr = max_dr
        elif dr < -max_dr:
            dr = -max_dr
        self._rate += dr
        # Integrar salida
        self._y += self._rate * dt
        self._y = clamp01(self._y)
        return self._y


__all__ = ["RateLimiter", "overspeed_guard", "clamp01", "JerkBrakeLimiter"]
