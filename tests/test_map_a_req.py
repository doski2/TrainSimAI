import pytest

from runtime.control_loop import _map_a_req_to_brake


@pytest.mark.real
def test_map_a_req_to_brake_mid():
    # Si a_req == a_service, val = 0.4 + 0.9 * (1) = 1.3 -> clipped a 1.0
    assert _map_a_req_to_brake(0.7, 0.7) == 1.0


@pytest.mark.real
def test_map_a_req_to_brake_small():
    # a_req muy pequeño -> valor menor que 0.4
    v = _map_a_req_to_brake(0.05, 0.7)
    assert v >= 0.0 and v <= 1.0
    assert v < 0.4


@pytest.mark.real
def test_map_a_req_invalid_inputs():
    assert _map_a_req_to_brake(float("nan"), 0.7) == 0.0
    assert _map_a_req_to_brake(0.5, float("nan")) == 0.0
