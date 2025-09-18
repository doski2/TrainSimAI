#!/usr/bin/env python3
"""Herramienta de verificación de base de datos SQLite.

Comprueba existencia, tamaño, integridad PRAGMA, modo de journal y frescura de los
últimos datos en la tabla `telemetry`.
"""

from __future__ import annotations

import argparse
import sqlite3
import time
from pathlib import Path
from typing import Optional


def inspect_db(path: Path, stale_threshold: float = 30.0) -> int:
    """Run a set of health checks on an SQLite database.

    Returns exit code: 0 OK, 1 runtime error, 2 missing file, 3 missing telemetry table
    """
    if not path.exists():
        print(f"[db_check] Database not found: {path}")
        return 2

    try:
        try:
            db_size = path.stat().st_size / (1024 * 1024)
            print(f"[db_check] Database size: {db_size:.2f} MB")
        except Exception as e:  # pragma: no cover - filesystem oddities
            print(f"[db_check] Could not stat DB file: {e}")

        with sqlite3.connect(path.as_posix(), timeout=10.0) as con:
            cur = con.cursor()

            # integrity_check
            try:
                cur.execute("PRAGMA integrity_check")
                integrity_row = cur.fetchone()
                integrity = integrity_row[0] if integrity_row else "UNKNOWN"
            except Exception as e:
                integrity = f"ERROR: {e}"
            print(f"[db_check] Integrity: {integrity}")

            # journal_mode
            try:
                cur.execute("PRAGMA journal_mode")
                jm = cur.fetchone()
                journal_mode = jm[0] if jm else "UNKNOWN"
            except Exception as e:
                journal_mode = f"ERROR: {e}"
            print(f"[db_check] Journal mode: {journal_mode}")

            # telemetry table exists?
            cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='telemetry'")
            has_tbl = (cur.fetchone() or [0])[0] > 0
            if not has_tbl:
                print("[db_check] DB existe pero NO hay tabla telemetry")
                return 3

            # rows and last row
            cur.execute("SELECT COUNT(*) FROM telemetry")
            n = (cur.fetchone() or [0])[0]
            print(f"[db_check] filas en telemetry: {n}")

            if n:
                cur.execute(
                    """
                    SELECT rowid, t_wall, odom_m, speed_kph
                    FROM telemetry ORDER BY rowid DESC LIMIT 1
                    """
                )
                last_row = cur.fetchone()
                print(f"[db_check] última fila: {last_row}")

                # Check freshness
                if last_row and len(last_row) > 1 and last_row[1] is not None:
                    try:
                        age = time.time() - float(last_row[1])
                        print(f"[db_check] data age: {age:.1f} seconds")
                        if age > stale_threshold:
                            print("[db_check] WARNING: Data is stale!")
                    except Exception:
                        print("[db_check] WARNING: Could not parse t_wall in last row")

    except Exception as e:
        print(f"[db_check] ERROR: {e}")
        return 1

    return 0


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="SQLite DB health checks for TrainSimAI")
    ap.add_argument("--db", default="data/run.db", help="Path to SQLite DB")
    ap.add_argument(
        "--stale-threshold",
        type=float,
        default=30.0,
        help="Seconds before telemetry is considered stale",
    )
    args = ap.parse_args(argv)
    return inspect_db(Path(args.db), stale_threshold=args.stale_threshold)


if __name__ == "__main__":
    raise SystemExit(main())
