import json
from pathlib import Path

from scripts.db_health_prometheus import render_prom_file


def test_prom_includes_control_status(tmp_path: Path):
    # prepare control_status.json
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    cs = {
        "last_command_time": 12345.6,
        "last_ack_time": 12346.0,
        "last_command_value": 0.75,
    }
    p = data_dir.joinpath("control_status.json")
    p.write_text(json.dumps(cs), encoding="utf-8")
    out = tmp_path.joinpath("trainsim_db.prom")
    render_prom_file("data/run.db", out)
    txt = out.read_text(encoding="utf-8")
    assert "trainsim_control_last_command_timestamp" in txt
    assert "trainsim_control_last_ack_timestamp" in txt
    assert "trainsim_control_last_command_value" in txt
    # labels
    assert "instance=" in txt
    assert "mode=" in txt
