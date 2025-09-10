from __future__ import annotations

import sqlite3
from pathlib import Path


def main(db: str = "data/run.db") -> None:
    p = Path(db)
    if not p.exists():
        print(f"[db_check] NO existe {db}")
        return
    con = sqlite3.connect(p.as_posix())
    cur = con.cursor()
    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='telemetry'")
    has_tbl = cur.fetchone()[0] > 0
    if not has_tbl:
        print("[db_check] DB existe pero NO hay tabla telemetry")
        return
    cur.execute("SELECT count(*) FROM telemetry")
    n = cur.fetchone()[0]
    print(f"[db_check] filas en telemetry: {n}")
    if n:
        cur.execute("SELECT rowid, t_wall, odom_m, speed_kph FROM telemetry ORDER BY rowid DESC LIMIT 1")
        print("[db_check] última fila:", cur.fetchone())


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/run.db")
    args = ap.parse_args()
    main(args.db)
