import gc
import tempfile
import time
from pathlib import Path

from storage import db_check


def test_db_check_connect_and_write():
    td = tempfile.TemporaryDirectory()
    dbfile = Path(td.name) / "health.db"
    # crear DB vacía
    dbfile.parent.mkdir(parents=True, exist_ok=True)
    # run_all_checks debe indicar connect ok y can_write ok
    res = db_check.run_all_checks(dbfile)
    assert res["connect"]["ok"] is True
    assert res["can_write"]["ok"] is True
    # pragmas deben estar presentes aunque sean None
    assert "pragmas" in res
    # asegurar cierre de handles en Windows antes de eliminar
    gc.collect()
    time.sleep(0.1)
    td.cleanup()
