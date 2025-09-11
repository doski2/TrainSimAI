from __future__ import annotations

import csv
import argparse
from pathlib import Path
from typing import Optional

from storage.run_store_sqlite import RunStore


def pick_delim(line: str) -> str:
    cands = [",", ";", "\t", "|"]
    counts = [(d, line.count(d)) for d in cands]
    d = max(counts, key=lambda t: t[1])[0]
    return d if line.count(d) > 0 else ","


def to_float_loose(s: Optional[str]) -> Optional[float]:
    if s is None:
        return None
    v = str(s).strip()
    if v == "" or v.lower() == "nan":
        return None
    # si contiene coma, asumimos coma decimal y puntos como separador de miles
    if "," in v:
        v = v.replace(".", "").replace(",", ".")
    else:
        # si hay más de un punto, probablemente son separadores de miles
        if v.count(".") > 1:
            v = v.replace(".", "")
    try:
        return float(v)
    except Exception:
        return None


def main(in_csv: str = "data/runs/run.csv", out_db: str = "data/run.db") -> None:
    p = Path(in_csv)
    if not p.exists():
        print(f"[migrate] no existe {in_csv}")
        return
    lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    if not lines:
        print(f"[migrate] fichero vacío {in_csv}")
        return
    first = lines[0]
    delim = pick_delim(first)
    store = RunStore(out_db)
    n = 0
    with p.open("r", encoding="utf-8", newline="") as f:
        rd = csv.DictReader(f, delimiter=delim)
        for r in rd:
            row = {
                "t_wall": to_float_loose(r.get("t_wall")),
                "odom_m": to_float_loose(r.get("odom_m")),
                "speed_kph": to_float_loose(r.get("speed_kph")),
                "next_limit_kph": to_float_loose(r.get("next_limit_kph")),
                "dist_next_limit_m": to_float_loose(r.get("dist_next_limit_m")),
                "meta": {},
            }
            if row["t_wall"] is None:
                continue
            store.insert_row(row)
            n += 1
    print(f"[migrate] insertadas {n} filas en {out_db}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Migrar run CSV a SQLite RunStore")
    ap.add_argument("--in", dest="in_csv", default="data/runs/run.csv")
    ap.add_argument("--out", dest="out_db", default="data/run.db")
    args = ap.parse_args()
    main(args.in_csv, args.out_db)
