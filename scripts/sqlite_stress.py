"""
Small SQLite stress tool to simulate concurrent writers and readers.

Usage (local):
    python -m scripts.sqlite_stress \
        --db tmp_run.db --writers 4 --readers 2 --duration 5 --interval 0.01

It writes telemetry rows and performs reads; results are summarized to stdout and
optionally written to an output JSON.
"""

from __future__ import annotations
import argparse
import sqlite3
import time
import threading
import random
import json
from pathlib import Path


def writer_thread(db_path: str, stop_at: float, stats: dict, tid: int, interval: float):
    conn = sqlite3.connect(db_path, timeout=0.1)
    cur = conn.cursor()
    # apply pragmatic PRAGMA tuning for concurrent access
    try:
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA busy_timeout=5000")
    except Exception:
        pass
    # ensure table (short SQL on one line but within limit)
    cur.execute(
        "CREATE TABLE IF NOT EXISTS telemetry (t_wall REAL, odom_m REAL, speed_kph REAL)"
    )
    conn.commit()
    while time.time() < stop_at:
        try:
            ts = time.time()
            odom = random.random() * 1000.0
            speed = random.random() * 120.0
            cur.execute("INSERT INTO telemetry (t_wall, odom_m, speed_kph) VALUES (?, ?, ?)", (ts, odom, speed))
            conn.commit()
            stats["writes"] += 1
        except Exception:
            stats["write_errors"] += 1
            time.sleep(0.001)
        time.sleep(interval)
    conn.close()


def reader_thread(db_path: str, stop_at: float, stats: dict, interval: float):
    conn = sqlite3.connect(db_path, timeout=0.1)
    cur = conn.cursor()
    try:
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA busy_timeout=5000")
    except Exception:
        pass
    while time.time() < stop_at:
        try:
            cur.execute("SELECT count(*) FROM telemetry")
            _ = cur.fetchone()
            stats["reads"] += 1
        except Exception:
            stats["read_errors"] += 1
            time.sleep(0.001)
        time.sleep(interval)
    conn.close()


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="tmp_run.db")
    p.add_argument("--writers", type=int, default=4)
    p.add_argument("--readers", type=int, default=2)
    p.add_argument("--duration", type=float, default=5.0)
    p.add_argument("--interval", type=float, default=0.01)
    p.add_argument("--out", default="artifacts/sqlite_stress.json")
    args = p.parse_args(argv)
    stop_at = time.time() + args.duration
    Path(args.db).unlink(missing_ok=True)
    stats = {"writes": 0, "reads": 0, "write_errors": 0, "read_errors": 0}
    ths = []
    for i in range(args.writers):
        th = threading.Thread(target=writer_thread, args=(args.db, stop_at, stats, i, args.interval), daemon=True)
        th.start()
        ths.append(th)
    for i in range(args.readers):
        th = threading.Thread(target=reader_thread, args=(args.db, stop_at, stats, args.interval), daemon=True)
        th.start()
        ths.append(th)
    try:
        while time.time() < stop_at:
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    for th in ths:
        th.join(timeout=1)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(stats), encoding="utf-8")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
