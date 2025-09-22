import csv
import importlib.util
import json
import sys
from pathlib import Path


def _import_drain(repo: Path):
    mod = repo / "tools" / "drain_lua_bus.py"
    spec = importlib.util.spec_from_file_location("drain", mod)
    drain = importlib.util.module_from_spec(spec)  # type: ignore
    sys.modules["drain"] = drain
    assert spec and spec.loader
    spec.loader.exec_module(drain)  # type: ignore
    return drain


def test_drain_incremental(tmp_path: Path):
    # estructura mínima
    (tmp_path / "data" / "events").mkdir(parents=True)
    (tmp_path / "data").mkdir(exist_ok=True)
    bus = tmp_path / "data" / "lua_eventbus.jsonl"
    out = tmp_path / "data" / "events" / "events.jsonl"
    # CSV con última geo
    runcsv = tmp_path / "data" / "runs.csv"  # usamos nombre distinto y monkeypatch
    runcsv.parent.mkdir(exist_ok=True)
    with runcsv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "lat",
                "lon",
                "time_ingame_h",
                "time_ingame_m",
                "time_ingame_s",
                "odom_m",
            ],
            delimiter=";",
        )
        w.writeheader()
        w.writerow(
            {
                "lat": 51.11,
                "lon": 13.60,
                "time_ingame_h": 18,
                "time_ingame_m": 6,
                "time_ingame_s": 2,
                "odom_m": 123.4,
            }
        )

    # escribir dos eventos al bus
    bus.write_text(
        (
            '{"type":"marker_pass","name":"m1","time":1}\n{"type":"marker_pass","name":"m2","time":2}\n'
        ),
        encoding="utf-8",
    )

    # importa el drain desde el repo real (padre del archivo de prueba)
    repo_root = Path(__file__).resolve().parents[1]
    drain = _import_drain(repo_root)

    # monkeypatch last_csv_row to use our runcsv
    def _last_csv_row(_repo):  # repo arg unused
        with runcsv.open("r", encoding="utf-8") as f:
            r = csv.DictReader(f, delimiter=";")
            rows = list(r)
            return rows[-1] if rows else {}

    drain.last_csv_row = _last_csv_row  # type: ignore

    state = tmp_path / "data" / ".lua_bus.offset"
    off0 = drain.load_offset(state, bus, from_start=False)
    lines, off1 = drain.iter_new_lines(bus, off0)
    assert len(lines) == 2 and off1 > off0

    # procesar y escribir
    events = []
    row = drain.last_csv_row(tmp_path)  # patched
    for line in lines:
        evt = json.loads(line)
        evt = drain.enrich(evt, row)
        events.append(drain.normalize(evt))
    out.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n",
        encoding="utf-8",
    )

    # reintento: nada nuevo
    lines2, off2 = drain.iter_new_lines(bus, off1)
    assert not lines2 and off2 == off1

    # comprobar geo enriquecida
    tail = out.read_text(encoding="utf-8").strip().splitlines()[-1]
    assert '"lat": 51.11' in tail and '"lon": 13.6' in tail
