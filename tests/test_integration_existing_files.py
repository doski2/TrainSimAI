from pathlib import Path
import json
import pandas as pd
import pytest


EV = Path("data/events/events.jsonl")
RUN = Path("data/runs/run.csv")
DIST = Path("data/runs/run.dist.csv")


def _read_jsonl(path: Path):
    out = []
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


@pytest.mark.integration
def test_events_have_meta_and_twall_if_present():
    if not EV.exists():
        pytest.skip("No hay data/events/events.jsonl en este entorno")
    ev = _read_jsonl(EV)
    gdn = [e for e in ev if str(e.get("type")) == "getdata_next_limit"]
    assert len(gdn) > 0, "No hay getdata_next_limit en events.jsonl"
    # Al menos uno debe tener t_wall y meta con to / dist_m
    ok = any(
        isinstance(e.get("t_wall"), (int, float))
        and isinstance((e.get("meta") or {}).get("to"), (int, float))
        and isinstance((e.get("meta") or {}).get("dist_m"), (int, float))
        for e in gdn
    )
    assert ok, "Faltan t_wall/meta.to/meta.dist_m en getdata_next_limit normalizados"


@pytest.mark.integration
def test_run_dist_has_column_if_present():
    if not DIST.exists():
        pytest.skip("No hay data/runs/run.dist.csv en este entorno")
    df = pd.read_csv(DIST)
    assert "dist_next_limit_m" in df.columns
    # Debe haber al menos un valor numérico
    assert df["dist_next_limit_m"].notna().any()

