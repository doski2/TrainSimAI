from __future__ import annotations
from pathlib import Path
from runtime.control_loop import tail_csv_last_row, _to_float_loose

def test_tail_csv_last_row_semicolon(tmp_path: Path):
    p = tmp_path / "run.csv"
    p.write_text(
        "t_wall;odom_m;speed_kph;next_limit_kph;dist_next_limit_m\n"
        "1757458752.0198007;10.0;5.0;;\n"
        "1757458752.1210198;20.0;6,50;;\n",  # coma decimal
        encoding="utf-8"
    )
    row = tail_csv_last_row(p)
    assert row is not None
    assert row["t_wall"] == "1757458752.1210198"
    # Convertimos con el helper tolerante
    assert _to_float_loose(row["speed_kph"]) == 6.50
