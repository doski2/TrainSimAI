from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any, Tuple


class RunStore:
    """SQLite store para telemetría en vivo (WAL, 1 writer + N readers)."""

    def __init__(self, db_path: str | Path = "data/run.db") -> None:
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.path.as_posix(), isolation_level=None, check_same_thread=False)
        self.con.execute("PRAGMA journal_mode=WAL")
        self.con.execute("PRAGMA synchronous=NORMAL")
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self.con.execute(
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
        self.con.execute("CREATE INDEX IF NOT EXISTS ix_telemetry_twall ON telemetry(t_wall)")

    def insert_row(self, row: Dict[str, Any]) -> None:
        meta = row.get("meta") or {}
        t = row.get("t_wall")
        if t is None:
            # t_wall es obligatorio; evita insertar filas sin sello de tiempo
            raise ValueError("t_wall is required")
        self.con.execute(
            "INSERT INTO telemetry(t_wall, odom_m, speed_kph, next_limit_kph, dist_next_limit_m, meta_json) VALUES(?,?,?,?,?,?)",
            (
                float(t),
                _f(row.get("odom_m")),
                _f(row.get("speed_kph")),
                _f(row.get("next_limit_kph")),
                _f(row.get("dist_next_limit_m")),
                json.dumps(meta, ensure_ascii=False),
            ),
        )

    def latest_since(self, last_rowid: int = 0) -> Optional[Tuple[int, Dict[str, Any]]]:
        cur = self.con.execute(
            "SELECT rowid, t_wall, odom_m, speed_kph, next_limit_kph, dist_next_limit_m "
            "FROM telemetry WHERE rowid > ? ORDER BY rowid DESC LIMIT 1",
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
