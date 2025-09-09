from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import numpy as np


def clamp(x: float, lo: float, hi: float) -> float:
    return min(hi, max(lo, x))


def kph_to_mps(v_kph: float) -> float:
    return float(v_kph) / 3.6


def mps_to_kph(v_mps: float) -> float:
    return float(v_mps) * 3.6


def effective_distance(
    dist_next_limit_m: Optional[float],
    v_now_mps: float,
    cfg: "BrakingConfig",
) -> float:
    """Distancia efectiva descontando el avance durante el tiempo de reacción.

    Si dist_next_limit_m es None o inválido, devuelve 0.0 (conservador).
    """
    try:
        d = float(dist_next_limit_m) if dist_next_limit_m is not None else 0.0
    except Exception:
        d = 0.0
    s_eff = d - float(v_now_mps) * float(cfg.reaction_time_s)
    return s_eff if s_eff > 0.0 else 0.0


@dataclass(frozen=True)
class BrakingConfig:
    """
    Parámetros de la regla de frenada v0 (conservadora).

    - margin_kph: margen por debajo del límite objetivo [km/h].
    - max_service_decel: deceleración de servicio [m/s^2] asumida para el cálculo.
    - reaction_time_s: tiempo de reacción [s] (se descuenta de la distancia efectiva).
    - coast_band_kph: banda muerta para mantener velocidad sin frenar [km/h].
    - min_target_kph: objetivo mínimo para evitar cero absoluto por ruido [km/h].
    """
    margin_kph: float = 3.0
    max_service_decel: float = 0.7
    reaction_time_s: float = 0.6
    coast_band_kph: float = 1.0
    min_target_kph: float = 5.0


__all__ = [
    "BrakingConfig",
    "compute_target_speed_kph",
    "clamp",
    "kph_to_mps",
    "mps_to_kph",
    "effective_distance",
]


def compute_target_speed_kph(
    current_v_kph: np.ndarray,
    dist_next_limit_m: np.ndarray,
    next_limit_kph: Optional[np.ndarray],
    cfg: BrakingConfig,
) -> np.ndarray:
    """
    Calcula la velocidad máxima permitida para garantizar que se puede
    alcanzar el próximo límite con una deceleración de servicio cfg.max_service_decel.

    Fórmula base: v_max^2 = v_lim_aj^2 + 2 * A * s_eff
      - v_lim_aj = max(0, (next_limit_kph - margin_kph)) en m/s
      - s_eff = max(0, dist_next_limit_m - v_ms * reaction_time_s)
    Devuelve v_max en km/h.
    """
    v_ms = np.asarray(current_v_kph, dtype=float) / 3.6
    dist = np.asarray(dist_next_limit_m, dtype=float)
    if next_limit_kph is None:
        lim_arr = np.full_like(dist, np.nan)
    else:
        lim_arr = np.asarray(next_limit_kph, dtype=float)
    s_eff = np.maximum(0.0, dist - v_ms * float(cfg.reaction_time_s))
    lim_adj_ms = np.maximum(0.0, (np.nan_to_num(lim_arr, nan=np.inf) - float(cfg.margin_kph)) / 3.6)
    v_max_ms = np.sqrt(
        np.clip(
            lim_adj_ms**2 + 2.0 * float(cfg.max_service_decel) * s_eff,
            a_min=0.0,
            a_max=np.inf,
        )
    )
    return v_max_ms * 3.6
