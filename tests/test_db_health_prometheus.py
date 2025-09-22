import gc
import tempfile
import time
from pathlib import Path

from scripts import db_health_prometheus


def test_db_health_prometheus_writes_file():
    td = tempfile.TemporaryDirectory()
    dbfile = Path(td.name) / "health.db"
    out = Path(td.name) / "trainsim_db.prom"
    db_health_prometheus.main([str(dbfile), "--out", str(out)])
    assert out.exists()
    txt = out.read_text(encoding="utf-8")
    assert "trainsim_db_connect_ok" in txt
    assert "trainsim_db_can_write" in txt
    # ensure handles released on Windows before cleanup
    gc.collect()
    time.sleep(0.1)
    td.cleanup()
