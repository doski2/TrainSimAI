import json
import time
from pathlib import Path

import pytest

from runtime.control_loop import ControlLoop


@pytest.mark.safety
def test_monitor_ack_timeout_triggers_emergency_and_clears(tmp_path, monkeypatch):
    """Integration-style test: apply a command, simulate ack timeout and verify emergency,
    then write an ack file and verify emergency is cleared.
    """
    # run inside a temp directory so control writes to data/* there
    monkeypatch.chdir(tmp_path)

    # provide a minimal run.csv so ControlLoop __init__ accepts source='csv'
    run_csv = tmp_path / "run.csv"
    run_csv.write_text("t_wall,odom_m,speed_kph\n0,0,0\n")

    ctl = ControlLoop(source="csv", run_csv=str(run_csv), ack_timeout_s=0.5)

    # initially not in emergency
    assert not ctl.emergency

    # send a brake command (this sets last_command_time)
    ctl.apply_brake_command(0.5)
    assert ctl.last_command_time is not None

    # simulate that the command was sent in the past beyond the ack timeout
    ctl.last_command_time = time.time() - (ctl.ack_timeout_s + 1.0)

    # running monitor should detect timeout and enter emergency
    ctl.monitor_ack_timeout()
    assert ctl.emergency is True

    # create an ack file with ts >= last_command_time to simulate actuator ack
    Path("data").mkdir(parents=True, exist_ok=True)
    # ensure ack timestamp is newer than the last command time
    ack_ts = time.time() + 10.0
    Path("data/rd_ack.json").write_text(json.dumps({"ts": ack_ts}), encoding="utf-8")

    # now monitor should observe the ack and clear emergency
    ctl.monitor_ack_timeout()
    assert ctl.emergency is False
