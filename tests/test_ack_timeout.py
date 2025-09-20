import time

from runtime.control_loop import ControlLoop


def test_ack_timeout_triggers_emergency():
    cl = ControlLoop(source='csv', run_csv='data/runs/run.csv', ack_timeout_s=0.05)
    # simulate sending a command
    cl.apply_brake_command(0.7)
    # immediately, no ack -> emergency should not yet be set
    cl.monitor_ack_timeout()
    assert cl.emergency is False
    # wait longer than ack_timeout and call monitor
    time.sleep(0.06)
    cl.monitor_ack_timeout()
    assert cl.emergency is True
    # provide ack and ensure emergency clears
    cl.ack_command()
    cl.monitor_ack_timeout()
    assert cl.emergency is False
