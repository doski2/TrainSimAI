import math
import pytest
from runtime.control_loop import _brake_distance_m


@pytest.mark.real
def test_brake_distance_basic():
    # De 100 kph a 50 kph con a=0.7 m/s2 y t_react=0.6 s
    d = _brake_distance_m(100.0, 50.0, 0.7, 0.6)
    # Calculamos manualmente la distancia de frenado esperada y comprobamos rango
    v = 100.0 / 3.6
    vt = 50.0 / 3.6
    dv = v - vt
    d_react = 0.6 * dv
    d_brake = max(0.0, (v * v - vt * vt) / (2.0 * 0.7))
    expected = d_react + d_brake
    assert math.isfinite(d)
    assert abs(d - expected) < 1e-6


@pytest.mark.real
def test_brake_distance_zero_decel():
    d = _brake_distance_m(80.0, 0.0, 0.0, 0.5)
    assert d == float("inf")
