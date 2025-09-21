#!/usr/bin/env python3
"""Create a minimal SQLite `data/run.db` with a `telemetry` table and one row
to allow tests that expect `data/run.db` to run in a fresh checkout.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
import time


def ensure_db(path: Path | str = "data/run.db") -> None:
    p = Path(path)
    if p.exists():
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(p) as conn:
        cur = conn.cursor()
        # Minimal telemetry table used by tests
        cur.execute(
            """
            CREATE TABLE telemetry (
                t_wall REAL,
                odom_m REAL,
                speed_kph REAL
            )
            """
        )
        # Insert a single recent row
        now = time.time()
        cur.execute("INSERT INTO telemetry (t_wall, odom_m, speed_kph) VALUES (?, ?, ?)", (now, 0.0, 0.0))
        conn.commit()


if __name__ == "__main__":
    ensure_db()
