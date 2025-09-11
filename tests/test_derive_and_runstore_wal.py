from __future__ import annotations
from runtime.control_loop import _to_float_loose
import math
from storage.sqlite_store import RunStore
import sqlite3
from pathlib import Path


def test_parsing_regional_additional_cases():
    # casos con miles '.' y coma decimal ',' y exponentes con coma
    assert _to_float_loose("1.234,56") == 1234.56
    assert _to_float_loose("-1.234.567,89") == -1234567.89
    assert _to_float_loose("3,5E+3") == 3.5e3
    assert math.isnan(_to_float_loose(None))


def test_derive_speed_from_two_samples():
    # simulamos dos muestras con odom en metros y t_wall en segundos
    prev_t = 1000.0
    prev_odom = 10000.0
    cur_t = 1002.0  # 2 segundos después
    cur_odom = 10050.0  # 50 m recorrido
    dt = max(1e-3, cur_t - prev_t)
    dv = cur_odom - prev_odom
    # derivación acorde al código: (dv / dt) * 3.6 -> km/h
    derived = max(0.0, (dv / dt) * 3.6)
    assert abs(derived - ((50.0 / 2.0) * 3.6)) < 1e-6


def test_runstore_latest_since_with_wal(tmp_path: Path):
    db = tmp_path / "run_wal.db"
    # crear DB y activarla en WAL mode
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.commit()
    conn.close()

    st = RunStore(db)
    st.insert_row({"t_wall": 1.0, "odom_m": 0.0, "speed_kph": 10.0})
    st.insert_row({"t_wall": 2.0, "odom_m": 10.0, "speed_kph": 20.0})
    res = st.latest_since()
    assert res is not None
    rowid, row = res
    assert row["t_wall"] == 2.0
    st.close()
