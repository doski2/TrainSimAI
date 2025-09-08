from __future__ import annotations

"""
Braking v1 (ERA): velocidad objetivo usando curva A(v) (m/s^2) dependiente de la velocidad.
Se integra distancia: d = ∫ v / a(v) dv, con búsqueda binaria para hallar v_safe.
Entrada de curva: CSV con columnas: speed_kph, decel_service_mps2
"""
from dataclasses import dataclass
from math import ceil
from pathlib import Path
from typing import List, Optional
import csv

from runtime.braking_v0 import BrakingConfig, kph_to_mps, mps_to_kph, effective_distance, clamp


def _lin_interp(x: float, xs: List[float], ys: List[float]) -> float:
    """Interpolación lineal y clamp en extremos."""
    n = len(xs)
    if n == 0:
        return 0.0
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    # búsqueda lineal sencilla (listas cortas); optimizable si hace falta
    for i in range(n - 1):
        x0, x1 = xs[i], xs[i + 1]
        if x0 <= x <= x1:
            t = (x - x0) / max(x1 - x0, 1e-9)
            return ys[i] * (1 - t) + ys[i + 1] * t
    return ys[-1]


@dataclass
class EraCurve:
    speeds_mps: List[float]          # ascendente
    decel_mps2: List[float]          # misma longitud
    min_decel_mps2: float = 0.1      # seguridad numérica

    @classmethod
    def from_csv(cls, path: str | Path) -> "EraCurve":
        p = Path(path)
        speeds_kph: List[float] = []
        decel: List[float] = []
        with p.open("r", encoding="utf-8") as f:
            rd = csv.DictReader(f)
            # esperamos: speed_kph, decel_service_mps2
            for row in rd:
                sk = row.get("speed_kph")
                a = row.get("decel_service_mps2") or row.get("decel_mps2") or row.get("A")
                if sk is None or a is None:
                    continue
                try:
                    vk = float(sk)
                    av = float(a)
                except Exception:
                    continue
                speeds_kph.append(vk)
                decel.append(av)
        # ordenar por velocidad
        z = sorted(zip(speeds_kph, decel), key=lambda t: t[0])
        speeds_mps = [kph_to_mps(vk) for vk, _ in z]
        decel_mps2 = [max(0.0, a) for _, a in z]
        return cls(speeds_mps, decel_mps2)

    def a_of_v(self, v_mps: float) -> float:
        a = _lin_interp(v_mps, self.speeds_mps, self.decel_mps2)
        return max(self.min_decel_mps2, float(a))

    def braking_distance(self, v0_kph: float, v_lim_kph: float, dv_mps: float = 0.2) -> float:
        """Distancia para ir de v0→v_lim integrando d = ∫ v/a(v) dv. (metros)"""
        v0 = kph_to_mps(max(v0_kph, v_lim_kph))
        vlim = kph_to_mps(v_lim_kph)
        if v0 <= vlim + 1e-6:
            return 0.0
        dv = max(1e-3, float(dv_mps))
        n = ceil((v0 - vlim) / dv)
        d = 0.0
        v_hi = v0
        for _ in range(n):
            v_lo = max(vlim, v_hi - dv)
            v_mid = 0.5 * (v_hi + v_lo)
            a = self.a_of_v(v_mid)
            d += (v_hi - v_lo) * (v_mid / a)
            v_hi = v_lo
        return d

    def v_safe_for_distance(self, d_eff_m: float, v_lim_kph: float, vmax_kph: float = 400.0) -> float:
        """Máxima v0_kph tal que la distancia para frenar a v_lim_kph ≤ d_eff_m (búsqueda binaria)."""
        lo = v_lim_kph
        hi = max(lo + 0.5, float(vmax_kph))
        for _ in range(40):
            mid = 0.5 * (lo + hi)
            d = self.braking_distance(mid, v_lim_kph)
            if d <= d_eff_m:
                lo = mid
            else:
                hi = mid
        return lo


def compute_target_speed_kph_era(
    v_now_kph: float,
    next_limit_kph: Optional[float],
    dist_next_limit_m: Optional[float],
    curve: EraCurve,
    *,
    gradient_pct: Optional[float] = None,
    cfg: BrakingConfig = BrakingConfig(),
) -> tuple[float, str]:
    """Devuelve (v_objetivo_kph, fase) usando curva ERA si hay próximo límite/distancia."""
    if next_limit_kph is None:
        return v_now_kph, "CRUISE"

    v_lim_kph = max(0.0, next_limit_kph - cfg.margin_kph)
    # distancia efectiva con tiempo de reacción (pendiente: tratada dentro de A(v) o ajuste externo si se desea)
    v_now_mps = kph_to_mps(max(0.0, v_now_kph))
    d_eff = effective_distance(dist_next_limit_m, v_now_mps, cfg)

    # v_safe por binaria sobre la curva
    v_safe_kph = curve.v_safe_for_distance(d_eff, v_lim_kph)
    v_obj_kph = clamp(min(v_now_kph, v_safe_kph), max(cfg.min_target_kph, 0.0), 400.0)

    # fase
    if v_obj_kph < v_now_kph - cfg.coast_band_kph:
        phase = "BRAKE"
    elif v_obj_kph <= v_now_kph + cfg.coast_band_kph:
        phase = "COAST"
    else:
        phase = "CRUISE"
    return v_obj_kph, phase

__all__ = ["EraCurve", "compute_target_speed_kph_era"]

