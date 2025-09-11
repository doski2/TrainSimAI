from __future__ import annotations

from runtime.braking_era import compute_target_speed_kph_era, EraCurve
from runtime.braking_v0 import BrakingConfig, kph_to_mps


CFG = BrakingConfig(margin_kph=1.5, max_service_decel=0.7, reaction_time_s=0.8)


def _simple_curve() -> EraCurve:
    # curva muy simple: 0 -> 200 km/h con deceleración constante (m/s^2)
    speeds_mps = [kph_to_mps(0.0), kph_to_mps(200.0)]
    decel_mps2 = [0.7, 0.7]
    return EraCurve(speeds_mps, decel_mps2)


def test_curve_equals_limit_at_zero_distance():
    v_now = 120.0
    limit = 80.0
    d = 0.0
    curve = _simple_curve()
    v_tgt, phase = compute_target_speed_kph_era(v_now, limit, d, curve, cfg=CFG)
    # con 0 m efectivos, el objetivo no debe exceder el límite (después de margen)
    assert v_tgt <= limit + 1e-6


def test_allowed_increases_with_distance():
    v_now = 140.0
    limit = 80.0
    d1, d2 = 100.0, 1000.0
    curve = _simple_curve()
    v1, _ = compute_target_speed_kph_era(v_now, limit, d1, curve, cfg=CFG)
    v2, _ = compute_target_speed_kph_era(v_now, limit, d2, curve, cfg=CFG)
    assert v2 >= v1


def test_phase_brake_when_target_below_now():
    v_now = 100.0
    limit = 80.0
    d = 200.0
    curve = _simple_curve()
    v_tgt, phase = compute_target_speed_kph_era(v_now, limit, d, curve, cfg=CFG)
    assert phase in ("BRAKE", "COAST")
