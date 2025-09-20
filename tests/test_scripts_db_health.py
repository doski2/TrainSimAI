import tempfile
from pathlib import Path
import gc
import time
from scripts import db_health


def test_db_health_exit_codes():
    td = tempfile.TemporaryDirectory()
    dbfile = Path(td.name) / "health.db"
    # run CLI runner programmatically
    code = db_health.run([str(dbfile)])
    assert code == 0
    # ensure file handles released on Windows before cleanup
    gc.collect()
    time.sleep(0.1)
    td.cleanup()
