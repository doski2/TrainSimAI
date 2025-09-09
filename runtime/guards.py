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


def overspeed_guard(speed_kph: float, limit_kph: float | None, *, delta_kph: float = 0.8) -> float:
    """Devuelve nivel mínimo de freno [0..1] cuando se excede el límite en delta_kph."""
    if limit_kph is None:
        return 0.0
    if speed_kph <= limit_kph + delta_kph:
        return 0.0
    # excesos mayores → más freno (rampa suave)
    exc = speed_kph - (limit_kph + delta_kph)
    # Rampa más agresiva: suelo 0.2 y +0.1 por cada 1 km/h extra
    return clamp01(0.2 + 0.1 * exc)


__all__ = ["RateLimiter", "overspeed_guard", "clamp01"]
