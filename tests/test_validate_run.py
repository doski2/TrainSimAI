import csv
from pathlib import Path

from tools import validate_run as vr


def test_reader_handles_semicolon_and_limits(tmp_path: Path):
    p = tmp_path / "run.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "provider",
                "product",
                "engine",
                "v_ms",
                "v_kmh",
                "t_wall",
                "Regulator",
                "VirtualBrake",
            ],
            delimiter=";",
        )
        w.writeheader()
        w.writerow(
            {
                "provider": "DTG",
                "product": "Dresden",
                "engine": "DB BR146.0",
                "v_ms": 10,
                "v_kmh": 36,
                "t_wall": 1,
                "Regulator": 0.1,
                "VirtualBrake": 0,
            }
        )
    fields, rows = vr.read_csv(str(p))
    assert "v_kmh" in (fields or []) and rows[-1]["Regulator"] == "0.1"
