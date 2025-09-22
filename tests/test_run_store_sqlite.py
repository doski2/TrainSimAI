from __future__ import annotations

from pathlib import Path

from storage import RunStore


def test_runstore_insert_and_latest(tmp_path: Path):
    db = tmp_path / "test_run.db"
    rs = RunStore(str(db))

    # empty DB -> latest_since should return None
    assert rs.latest_since(0) is None

    # insert a valid row
    row = {
        "t_wall": 1.0,
        "odom_m": 100.0,
        "speed_kph": 36.0,
        "next_limit_kph": 50.0,
        "dist_next_limit_m": 500.0,
        "meta": {"src": "test"},
    }
    rs.insert_row(row)

    # after insert, latest_since(0) should return the row
    latest = rs.latest_since(0)
    assert latest is not None
    rowid, data = latest
    assert data["t_wall"] == 1.0
    assert abs(data["speed_kph"] - 36.0) < 1e-6

    # insert a second row
    row2 = row.copy()
    row2["t_wall"] = 2.0
    row2["odom_m"] = 110.0
    rs.insert_row(row2)

    latest2 = rs.latest_since(rowid)
    assert latest2 is not None
    rowid2, data2 = latest2
    assert data2["t_wall"] == 2.0

    rs.close()


def test_runstore_skip_missing_t_wall(tmp_path: Path):
    db = tmp_path / "test_run2.db"
    rs = RunStore(str(db))

    # insert row without t_wall should raise or be ignored
    bad_row = {"odom_m": 1.0}
    try:
        rs.insert_row(bad_row)
    except Exception:
        # acceptable behavior is to raise; ensure DB still works
        pass

    # DB should still be operational and empty
    assert rs.latest_since(0) is None
    rs.close()
