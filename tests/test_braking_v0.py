from __future__ import annotations

from runtime.braking_era import compute_target_speed_kph_era

# Config v0 (dict). Ajusta si tu perfil difiere.
CFG = {
    "a_service_mps2": 0.7,
    "t_react_s": 0.8,
    "margin_m": 70.0,
    "v_margin_kph": 2.0,
}


def test_curve_equals_limit_at_zero_distance():
    v_now = 120.0
    limit = 80.0
    d = 0.0
    v_tgt, phase = compute_target_speed_kph_era(v_now, limit, d, curve=None, cfg=CFG)
    # Cerca del hito (0m), no debemos exceder el límite
    assert v_tgt <= limit + 1e-6


def test_allowed_increases_with_distance():
    v_now = 200.0  # alto para no ser el factor limitante
    limit = 80.0
    d1, d2 = 100.0, 1000.0
    v1, _ = compute_target_speed_kph_era(v_now, limit, d1, curve=None, cfg=CFG)
    v2, _ = compute_target_speed_kph_era(v_now, limit, d2, curve=None, cfg=CFG)
    assert v2 >= v1


def test_phase_brake_when_target_below_now():
    v_now = 100.0
    limit = 80.0
    d = 200.0
    v_tgt, phase = compute_target_speed_kph_era(v_now, limit, d, curve=None, cfg=CFG)
    assert phase in ("BRAKE", "COAST")
