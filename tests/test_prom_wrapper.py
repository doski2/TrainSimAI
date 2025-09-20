from pathlib import Path

from scripts import db_health_prometheus as prom


def test_render_prom_file(tmp_path: Path, monkeypatch):
    # monkeypatch run_all_checks to a predictable result
    def fake_run_all_checks(db):
        return {"connect": {"ok": True}, "can_write": {"ok": False}}

    monkeypatch.setattr("storage.db_check.run_all_checks", fake_run_all_checks)

    out = tmp_path / "trainsim_db.prom"
    prom.render_prom_file("/tmp/fake.db", out)

    text = out.read_text(encoding="utf-8")
    assert "trainsim_db_connect_ok" in text
    assert "trainsim_db_can_write" in text
    # connect ok -> value 1
    assert 'trainsim_db_connect_ok{db="/tmp/fake.db"} 1' in text
    # write failed -> value 0
    assert 'trainsim_db_can_write{db="/tmp/fake.db"} 0' in text
