from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable

import sys

# Asegura que el repo raíz esté en sys.path
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from runtime.events_bus import normalize
import csv


def iter_jsonl(path: Path) -> Iterable[dict]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            yield obj


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    in_path = repo / "data" / "lua_eventbus.jsonl"
    out_path = repo / "data" / "events" / "events.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Lee última fila del CSV para enriquecer eventos (lat/lon/tiempo)
    last_row = {}
    csv_path = repo / "data" / "runs" / "run.csv"
    if csv_path.exists():
        try:
            with csv_path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
                r = csv.DictReader(f, delimiter=";")
                for row in r:
                    last_row = row  # nos quedamos con la última
        except Exception:
            last_row = {}

    n = 0
    with out_path.open("a", encoding="utf-8") as out:
        for obj in iter_jsonl(in_path):
            # Completa lat/lon si faltan en el evento
            if obj.get("lat") is None and last_row.get("lat"):
                obj["lat"] = float(last_row["lat"])
            if obj.get("lon") is None and last_row.get("lon"):
                obj["lon"] = float(last_row["lon"])
            # Si no trae 'time', intenta construirlo desde H/M/S del CSV
            if obj.get("time") is None:
                try:
                    h = float(last_row.get("time_ingame_h") or 0)
                    m = float(last_row.get("time_ingame_m") or 0)
                    s = float(last_row.get("time_ingame_s") or 0)
                    obj["time"] = h + m/60.0 + s/3600.0  # horas decimales
                except Exception:
                    pass
            nrm = normalize(obj)
            out.write(json.dumps(nrm, ensure_ascii=False) + "\n")
            n += 1
    print(f"[drain] Escribidos {n} eventos normalizados en {out_path}")


if __name__ == "__main__":
    main()
