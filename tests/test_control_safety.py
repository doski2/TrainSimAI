import time

from runtime.control_loop import ControlLoop, _map_a_req_to_brake


def test_map_a_req_to_brake_bounds():
    # a_req negative -> brake 0
    assert _map_a_req_to_brake(-1.0, 1.0) == 0.0
    # very large a_req -> capped at 1.0
    assert _map_a_req_to_brake(1000.0, 1.0) == 1.0
    # reasonable value
    v = _map_a_req_to_brake(0.5, 1.0)
    assert 0.0 <= v <= 1.0


def test_apply_brake_clamps_and_returns():
    cl = ControlLoop(source="csv", run_csv="data/runs/run.csv", hz=1)
    assert cl.apply_brake_command(0.5) == 0.5
    assert cl.apply_brake_command(1.5) == 1.0
    assert cl.apply_brake_command(float("nan")) == 0.0
    assert cl.apply_brake_command(-0.2) == 0.0


def test_stale_data_detection():
    cl = ControlLoop(source="csv", run_csv="data/runs/run.csv", hz=1, stale_data_threshold=0.5)
    # data with missing t_wall -> stale
    assert cl.is_data_stale({}) is True
    # data with future t_wall -> fresh
    future = {"t_wall": str(time.time() + 0.1)}
    assert cl.is_data_stale(future) is False
    # data with old t_wall -> stale
    old = {"t_wall": str(time.time() - 10)}
    assert cl.is_data_stale(old) is True
