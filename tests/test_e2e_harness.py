import json
import threading
import time
from pathlib import Path

import runtime.raildriver_stub as rd_stub
from runtime.control_loop import ControlLoop


def _write_run_csv(row: dict):
    p = Path("data/runs/run.csv")
    p.parent.mkdir(parents=True, exist_ok=True)
    header = ",".join(row.keys()) + "\n"
    line = ",".join(str(v) for v in row.values()) + "\n"
    # create minimal csv with header+row
    p.write_text(header + line, encoding="utf-8")


def actuator_watcher(stop_event: threading.Event):
    """Thread that watches control_status.json and invokes rd_stub when new command appears."""
    last_cmd_ts: float = 0.0
    while not stop_event.is_set():
        p = Path("data/control_status.json")
        if p.exists():
            try:
                cur = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                cur = {}
            ts = float(cur.get("last_command_time") or 0)
            val = cur.get("last_command_value")
            if ts and ts > last_cmd_ts and val is not None:
                # simulate actuator applying the brake and ack via rd_stub
                rd_stub.rd.set_brake(val)
                last_cmd_ts = ts
        time.sleep(0.02)


def test_e2e_simple_flow():
    # prepare a run.csv row that instructs a_req so ControlLoop applies a brake
    row = {
        "t_wall": time.time(),
        "odom_m": 0.0,
        "speed_kph": 80.0,
        "a_req": -1.0,
        "a_service": 1.0,
    }
    _write_run_csv(row)

    # start actuator watcher thread
    stop_event = threading.Event()
    th = threading.Thread(target=actuator_watcher, args=(stop_event,), daemon=True)
    th.start()

    # run control loop one iteration using csv source
    cl = ControlLoop(source="csv", run_csv="data/runs/run.csv", hz=20, ack_timeout_s=1.0)
    # run only a short time in another thread to avoid blocking
    t = threading.Thread(target=cl.run, daemon=True)
    t.start()

    # let loop run and watcher ack
    time.sleep(0.5)

    # check that control_status.json exists and has last_ack_time
    p = Path("data/control_status.json")
    assert p.exists()
    txt = json.loads(p.read_text(encoding="utf-8"))
    assert "last_command_time" in txt
    assert "last_ack_time" in txt

    # stop threads
    cl.stop()
    stop_event.set()
    t.join(timeout=1)
    th.join(timeout=1)
