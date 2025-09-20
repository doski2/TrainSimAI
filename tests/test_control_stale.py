import time
# no extra imports needed

from runtime.control_loop import ControlLoop


def make_fake_csv(path, t_wall):
    with open(path, "w") as f:
        f.write("t_wall,odom_m,speed_kph\n")
        f.write(f"{t_wall},100.0,80.0\n")


def test_stale_detection_skips_processing(tmp_path, monkeypatch, caplog):
    csv = tmp_path / "run.csv"
    # poner timestamp muy antiguo
    old_t = time.time() - 3600.0
    make_fake_csv(csv, old_t)

    cl = ControlLoop(source="csv", run_csv=str(csv), hz=5, stale_data_threshold=2.0)
    # Leer una fila
    data = cl.read_telemetry()
    assert data is not None
    # is_data_stale debe detectar que es viejo
    assert cl.is_data_stale(data) is True


def test_stale_detection_accepts_recent(tmp_path):
    csv = tmp_path / "run.csv"
    t = time.time()
    make_fake_csv(csv, t)
    cl = ControlLoop(source="csv", run_csv=str(csv), hz=5, stale_data_threshold=5.0)
    data = cl.read_telemetry()
    assert data is not None
    assert cl.is_data_stale(data) is False
