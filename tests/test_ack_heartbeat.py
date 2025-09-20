import time
from pathlib import Path

from runtime.control_loop import ControlLoop


def test_apply_updates_status_file(tmp_path: Path):
    # use tmp dir as cwd
    try:
        Path("data").mkdir(exist_ok=True)
        cl = ControlLoop(source="csv", run_csv="data/runs/run.csv")
        sent = cl.apply_brake_command(0.33)
        assert 0.0 <= sent <= 1.0
        p = Path("data/control_status.json")
        assert p.exists()
        data = p.read_text(encoding="utf-8")
        assert "last_command_time" in data
        assert "last_command_value" in data
    finally:
        # cleanup
        try:
            Path("data/control_status.json").unlink()
        except Exception:
            pass


def test_ack_updates_status_file():
    cl = ControlLoop(source="csv", run_csv="data/runs/run.csv")
    cl.apply_brake_command(0.5)
    time.sleep(0.01)
    cl.ack_command()
    p = Path("data/control_status.json")
    assert p.exists()
    txt = p.read_text(encoding="utf-8")
    assert "last_ack_time" in txt
