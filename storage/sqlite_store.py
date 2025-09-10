from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import sqlite3
import json


class RunStore:
    """Minimal SQLite-backed store for telemetry rows.

    API:
    - insert_row(row: Dict[str, Any]) -> None
    - latest_since(last_rowid: int) -> Optional[Tuple[int, Dict[str, Any]]]
    - close()
    """

    def __init__(self, db_path: str | Path = "data/tsc_runs.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # autocommit mode, allow access from threads
        self.con = sqlite3.connect(str(self.db_path), isolation_level=None, check_same_thread=False)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        cur = self.con.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS telemetry (
                t_wall REAL NOT NULL,
                odom_m REAL,
                speed_kph REAL,
                next_limit_kph REAL,
                dist_next_limit_m REAL,
                meta_json TEXT
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS ix_telemetry_twall ON telemetry(t_wall)")
        cur.close()

    def insert_row(self, row: Dict[str, Any]) -> None:
        meta = row.get("meta") or {}
        self.con.execute(
            "INSERT INTO telemetry(t_wall, odom_m, speed_kph, next_limit_kph, dist_next_limit_m, meta_json) VALUES(?,?,?,?,?,?)",
            (
                _f(row.get("t_wall")),
                _f(row.get("odom_m")),
                _f(row.get("speed_kph")),
                _f(row.get("next_limit_kph")),
                _f(row.get("dist_next_limit_m")),
                json.dumps(meta, ensure_ascii=False),
            ),
        )

    def latest_since(self, last_rowid: int = 0) -> Optional[Tuple[int, Dict[str, Any]]]:
        cur = self.con.execute(
            "SELECT rowid, t_wall, odom_m, speed_kph, next_limit_kph, dist_next_limit_m FROM telemetry WHERE rowid > ? ORDER BY rowid DESC LIMIT 1",
            (int(last_rowid),),
        )
        r = cur.fetchone()
        if not r:
            return None
        rowid, t, od, sp, lim, dist = r
        return rowid, {
            "t_wall": float(t),
            "odom_m": _f(od),
            "speed_kph": _f(sp),
            "next_limit_kph": _f(lim),
            "dist_next_limit_m": _f(dist),
        }

    def close(self) -> None:
        try:
            self.con.close()
        except Exception:
            pass


def _f(x: Any) -> Optional[float]:
    try:
        return None if x is None else float(x)
    except Exception:
        return None


__all__ = ["RunStore"]
