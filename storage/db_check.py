from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Dict, Any, Tuple


def check_connect(db_path: str | Path, timeout: float = 5.0) -> Tuple[bool, str]:
    """Intenta abrir la conexión y ejecutar una consulta trivial."""
    try:
        with sqlite3.connect(str(db_path), timeout=timeout) as con:
            cur = con.execute("SELECT 1")
            _ = cur.fetchone()
        return True, "ok"
    except Exception as e:
        return False, f"connect-error: {e}"


def check_can_write(db_path: str | Path, timeout: float = 5.0) -> Tuple[bool, str]:
    """
    Intenta realizar una transacción de escritura que se revierte
    (begin/rollback) para comprobar locks y permisos.
    """
    try:
        con = sqlite3.connect(str(db_path), timeout=timeout)
        try:
            cur = con.cursor()
            cur.execute("BEGIN IMMEDIATE")
            # intentar escribir en una tabla conocida; si tabla no existe, crear y borrar
            cur.execute("CREATE TABLE IF NOT EXISTS __health_tmp(t INT)")
            cur.execute("INSERT INTO __health_tmp(t) VALUES(1)")
            con.rollback()
            return True, "ok"
        finally:
            con.close()
    except sqlite3.OperationalError as e:
        return False, f"operational-error: {e}"
    except Exception as e:
        return False, f"write-error: {e}"


def read_pragmas(db_path: str | Path, timeout: float = 5.0) -> Dict[str, Any]:
    """Lee pragmas básicos (journal_mode, synchronous, busy_timeout) y los devuelve."""
    res = {"journal_mode": None, "synchronous": None, "busy_timeout": None}
    try:
        with sqlite3.connect(str(db_path), timeout=timeout) as con:
            cur = con.execute("PRAGMA journal_mode")
            r = cur.fetchone()
            if r:
                res["journal_mode"] = r[0]
            cur = con.execute("PRAGMA synchronous")
            r = cur.fetchone()
            if r:
                res["synchronous"] = r[0]
            cur = con.execute("PRAGMA busy_timeout")
            r = cur.fetchone()
            if r:
                res["busy_timeout"] = r[0]
    except Exception:
        pass
    return res


def run_all_checks(db_path: str | Path) -> Dict[str, Any]:
    """Convenience runner que ejecuta checks y devuelve el resumen."""
    out: Dict[str, Any] = {}
    ok, msg = check_connect(db_path)
    out["connect"] = {"ok": ok, "msg": msg}
    ok, msg = check_can_write(db_path)
    out["can_write"] = {"ok": ok, "msg": msg}
    out["pragmas"] = read_pragmas(db_path)
    out["timestamp"] = time.time()
    return out


__all__ = ["check_connect", "check_can_write", "read_pragmas", "run_all_checks"]
