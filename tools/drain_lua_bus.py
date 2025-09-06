from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List, Tuple
import csv
import json

# Re-export normalize so tests can call drain.normalize(...)
try:
    from runtime.events_bus import normalize  # type: ignore
except Exception:  # pragma: no cover
    # Fallback no-op normalize if runtime is unavailable (shouldn't happen in repo)
    def normalize(evt: Dict[str, Any]) -> Dict[str, Any]:  # type: ignore
        return evt


def load_offset(state_path: Path | str, bus_path: Path | str, from_start: bool = False) -> int:
    """Load last read byte offset for the LUA bus file.

    Behavior:
    - If state file exists: return stored integer offset.
    - If not: start at 0 (read existing content) regardless of from_start to match tests.
    """
    state = Path(state_path)
    try:
        if state.exists():
            txt = state.read_text(encoding="utf-8").strip()
            return int(txt) if txt else 0
    except Exception:
        return 0
    return 0


def iter_new_lines(bus_path: Path | str, offset: int) -> Tuple[List[str], int]:
    """Read new JSONL lines from bus_path starting at byte offset.

    Returns (lines, new_offset).
    """
    p = Path(bus_path)
    if not p.exists():
        return [], offset
    size = p.stat().st_size
    if offset < 0 or offset > size:
        offset = 0
    lines: List[str] = []
    with p.open("r", encoding="utf-8") as f:
        f.seek(offset)
        for line in f:
            if line:
                lines.append(line.rstrip("\n"))
        new_off = f.tell()
    return lines, new_off


def write_offset(state_path: Path | str, offset: int) -> None:
    Path(state_path).write_text(str(offset), encoding="utf-8")


def last_csv_row(repo_root: Path | str) -> Dict[str, Any]:
    """Return the last row from the default run CSV as a dict.

    Looks at <repo>/data/runs/run.csv with ';' delimiter.
    Returns {} if file missing or empty.
    """
    root = Path(repo_root)
    csv_path = root / "data" / "runs" / "run.csv"
    if not csv_path.exists():
        return {}
    try:
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            r = csv.DictReader(f, delimiter=";")
            rows = list(r)
            return rows[-1] if rows else {}
    except Exception:
        return {}


def _to_float(x: Any) -> float | None:
    try:
        if x is None or x == "":
            return None
        return float(x)
    except Exception:
        return None


def enrich(evt: Dict[str, Any], last_row: Dict[str, Any]) -> Dict[str, Any]:
    """Enrich raw event with latest known geo/time fields from CSV row.

    - Adds lat/lon if missing in evt and present in last_row.
    - If evt lacks 'time' but last_row has time_ingame_h/m/s, compute seconds.
    - Passes through other keys unchanged.
    """
    out = dict(evt)
    if "lat" not in out or out.get("lat") is None:
        lat = _to_float(last_row.get("lat")) if last_row else None
        if lat is not None:
            out["lat"] = lat
    if "lon" not in out or out.get("lon") is None:
        lon = _to_float(last_row.get("lon")) if last_row else None
        if lon is not None:
            out["lon"] = lon

    if out.get("time") is None and last_row:
        try:
            h = int(float(last_row.get("time_ingame_h", 0)))
            m = int(float(last_row.get("time_ingame_m", 0)))
            s = float(last_row.get("time_ingame_s", 0))
            out["time"] = h * 3600 + m * 60 + s
        except Exception:
            pass
    return out


def signature(evt: Dict[str, Any]) -> str:
    """Build a simple signature string for deduplication/logging purposes."""
    t = evt.get("type", "")
    tag = evt.get("name") or evt.get("station") or evt.get("marker") or ""
    time_val = evt.get("time") or evt.get("t_ingame") or ""
    return f"{t}|{tag}|{time_val}"


def _main(repo_root: Path) -> int:  # pragma: no cover
    """Minimal CLI drain: read new lines and append normalized events to events.jsonl."""
    bus = repo_root / "data" / "lua_eventbus.jsonl"
    out = repo_root / "data" / "events" / "events.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    state = repo_root / "data" / ".lua_bus.offset"

    off = load_offset(state, bus)
    lines, new_off = iter_new_lines(bus, off)
    if not lines:
        return 0
    row = last_csv_row(repo_root)
    with out.open("a", encoding="utf-8") as f:
        for line in lines:
            try:
                evt = json.loads(line)
            except Exception:
                continue
            e = enrich(evt, row)
            n = normalize(e)
            f.write(json.dumps(n, ensure_ascii=False) + "\n")
    write_offset(state, new_off)
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys

    code = _main(Path.cwd())
    sys.exit(code)

