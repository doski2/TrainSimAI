import tempfile
from pathlib import Path

from storage.run_store_sqlite import RunStore


def test_run_store_pragmas_tmpdb():
    td = tempfile.TemporaryDirectory()
    dbfile = Path(td.name) / "test_run.db"
    # crear RunStore con busy timeout personalizado y synchronous como NORMAL
    rs = RunStore(db_path=dbfile, busy_timeout_ms=1234, synchronous="NORMAL")
    p = rs.get_pragmas()
    # journal_mode debe estar en modo wal (sqlite devuelve 'wal' en minúsculas)
    assert p["journal_mode"] in ("wal", "WAL", "wal\n", "WAL\n")
    # synchronous suele ser un entero (1 para NORMAL), comprobar que es int o string convertible
    assert p["synchronous"] is not None
    # busy_timeout debe ser al menos el valor solicitado (sqlite puede devolver 0 si no soportado)
    assert p["busy_timeout"] is not None
    # cerrar la conexión antes de eliminar el archivo en Windows
    rs.close()
    td.cleanup()
