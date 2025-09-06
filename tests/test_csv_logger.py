from pathlib import Path
from typing import List, cast
from runtime.csv_logger import CsvLogger
import csv


def test_csv_header_and_extension(tmp_path: Path):
    p = tmp_path / "run.csv"
    log = CsvLogger(str(p))
    # primar cabecera con superset (simula rd.schema())
    fields = [
        "provider",
        "product",
        "engine",
        "v_ms",
        "v_kmh",
        "Regulator",
        "VirtualBrake",
        "t_wall",
    ]
    log.init_with_fields(fields)

    # 1ª fila (subset)
    log.write_row({
        "provider": "DTG",
        "product": "Dresden",
        "engine": "DB BR146.0",
        "v_ms": 10,
        "v_kmh": 36,
        "t_wall": 1.0,
    })
    # 2ª fila añade columnas nuevas
    log.write_row({
        "Regulator": 0.25,
        "VirtualBrake": 0.0,
        "v_ms": 11,
        "v_kmh": 39.6,
        "t_wall": 2.0,
    })

    # leer y verificar
    with p.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f, delimiter=";")
        cols = cast(List[str], r.fieldnames or [])
        rows = list(r)
    assert set(fields).issubset(set(cols))
    assert rows[-1]["Regulator"] == "0.25"
    assert rows[-1]["VirtualBrake"] == "0.0"
