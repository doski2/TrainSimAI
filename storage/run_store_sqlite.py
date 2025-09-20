from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any, Tuple


class RunStore:
    """SQLite store para telemetría en vivo (WAL, 1 writer + N readers)."""

    def __init__(
        self,
        db_path: str | Path = "data/run.db",
        busy_timeout_ms: int = 5000,
        synchronous: int | str = "NORMAL",
    ) -> None:
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # abrir con check_same_thread=False para permitir accesos desde hilos diferentes
        self.con = sqlite3.connect(
            self.path.as_posix(), isolation_level=None, check_same_thread=False
        )
        # aplicar pragmas de robustez
        # journal_mode: preferimos WAL para múltiples lectores concurrentes
        try:
            self.con.execute("PRAGMA journal_mode=WAL")
        except Exception:
            pass
        # busy_timeout en milisegundos
        try:
            self.con.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
        except Exception:
            pass
        # synchronous puede ser int 0..3 o texto como NORMAL/EXTRA
        try:
            if isinstance(synchronous, int):
                self.con.execute(f"PRAGMA synchronous={int(synchronous)}")
            else:
                self.con.execute(f"PRAGMA synchronous={str(synchronous)}")
        except Exception:
            pass
        self._ensure_schema()

    def get_pragmas(self) -> Dict[str, Any]:
        """Leer algunos pragmas de la conexión para pruebas/diagnóstico."""
        cur = self.con.execute("PRAGMA journal_mode")
        journal = cur.fetchone()[0] if cur is not None else None
        cur = self.con.execute("PRAGMA synchronous")
        sync = cur.fetchone()[0] if cur is not None else None
        cur = self.con.execute("PRAGMA busy_timeout")
        busy = cur.fetchone()[0] if cur is not None else None
        return {"journal_mode": journal, "synchronous": sync, "busy_timeout": busy}

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
            "INSERT INTO telemetry(t_wall, odom_m, speed_kph, next_limit_kph, "
            "dist_next_limit_m, meta_json) VALUES(?,?,?,?,?,?)",
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
