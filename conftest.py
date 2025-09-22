import sqlite3
import time
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def ensure_test_db():
    """Ensure a minimal data/run.db exists for tests that expect it.

    This fixture is autouse to avoid requiring tests to explicitly request it
    (convenient for legacy tests that expect the file to be present).
    """
    p = Path("data/run.db")
    if p.exists():
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(p) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE telemetry (
                t_wall REAL,
                odom_m REAL,
                speed_kph REAL
            )
            """
        )
        now = time.time()
        cur.execute(
            "INSERT INTO telemetry (t_wall, odom_m, speed_kph) VALUES (?, ?, ?)",
            (now, 0.0, 0.0),
        )
        conn.commit()
