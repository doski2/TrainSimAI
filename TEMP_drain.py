# tools/drain_lua_bus.py
from __future__ import annotations
import argparse, os, json, time, csv
from pathlib import Path
from typing import Iterable, Dict, Any, Optional
from runtime.events_bus import normalize

def load_offset(state_path: Path, bus_path: Path, from_start: bool) -> int:
    if state_path.exists():
        try:
            return int(state_path.read_text().strip())
        except Exception:
            pass
    # por defecto: desde el final (no re-procesar histórico)
    return 0 if from_start else (bus_path.stat().st_size if bus_path.exists() else 0)

def save_offset(state_path: Path, pos: int) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(str(pos))

def iter_new_lines(bus_path: Path, offset: int) -> tuple[list[str], int]:
    out: list[str] = []
    if not bus_path.exists():
        return out, offset
    with bus_path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        f.seek(offset)
        for line in f:
            line = line.strip()
            if line:
                out.append(line)
        offset = f.tell()
    return out, offset

def last_csv_row(repo: Path) -> Dict[str, Any]:
    csv_path = repo / "data" / "runs" / "run.csv"
    row: Dict[str, Any] = {}
    if not csv_path.exists():
        return row
    try:
        csv.field_size_limit(50 * 1024 * 1024)
        with csv_path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
            r = csv.DictReader(f, delimiter=";")
            for rr in r:
                row = rr
    except Exception:
        pass
    return row

def enrich(evt: Dict[str, Any], row: Dict[str, Any]) -> Dict[str, Any]:
    e = dict(evt)
    if e.get("lat") in (None, "", "null") and row.get("lat"):
        e["lat"] = float(row["lat"])
    if e.get("lon") in (None, "", "null") and row.get("lon"):
        e["lon"] = float(row["lon"])
    if e.get("time") is None:
        try:
            h = float(row.get("time_ingame_h") or 0)
            m = float(row.get("time_ingame_m") or 0)
            s = float(row.get("time_ingame_s") or 0)
            e["time"] = h + m/60.0 + s/3600.0
        except Exception:
            pass
    if "odom_m" not in e and row.get("odom_m") is not None:
        try:
            e["odom_m"] = float(row["odom_m"])
        except Exception:
            pass
    e["source"] = e.get("source") or "drain"
    return e

def signature(evt: Dict[str, Any]) -> tuple:
    ident = evt.get("marker") or evt.get("station") or evt.get("payload")
    return (evt.get("type"), ident, evt.get("time"))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-start", action="store_true", help="Procesa el bus desde el inicio (por defecto desde el final)")
    parser.add_argument("--follow", action="store_true", help="Sigue esperando nuevas líneas (modo watch)")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    bus_path = repo / "data" / "lua_eventbus.jsonl"
    out_path = repo / "data" / "events" / "events.jsonl"
    state_path = repo / "data" / ".lua_bus.offset"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    offset = load_offset(state_path, bus_path, args.from_start)
    seen: set[tuple] = set()

    while True:
        lines, offset = iter_new_lines(bus_path, offset)
        if lines:
            row = last_csv_row(repo)
            with out_path.open("a", encoding="utf-8") as out:
                for line in lines:
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    evt = enrich(obj, row)
                    sig = signature(evt)
                    if sig in seen:
                        continue
                    seen.add(sig)
                    nrm = normalize(evt)
                    out.write(json.dumps(nrm, ensure_ascii=False) + "\n")
            save_offset(state_path, offset)
            print(f"[drain] procesadas {len(lines)} línea(s); offset={offset}")
        if not args.follow:
            break
        time.sleep(0.1)

if __name__ == "__main__":
    main()

