from __future__ import annotations

from pathlib import Path
from storage.sqlite_store import RunStore


def test_insert_and_latest(tmp_path: Path):
    db = tmp_path / "run.db"
    st = RunStore(db)
    st.insert_row({"t_wall": 1.0, "odom_m": 10.0, "speed_kph": 20.0})
    st.insert_row({"t_wall": 2.0, "odom_m": 11.0, "speed_kph": 21.0})
    res = st.latest_since()
    assert res is not None
    rowid, row = res
    assert row["t_wall"] == 2.0
    assert row["speed_kph"] == 21.0
