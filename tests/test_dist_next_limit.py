import json
from pathlib import Path
import pytest
import pandas as pd


@pytest.mark.skipif(
    False, reason="always run; will skip internally if helper not present"
)
def test_dist_from_getdata_probes_alignment(tmp_path: Path):
    # 1) DataFrame de ejemplo (como run.csv) con t_wall
    df = pd.DataFrame({
        "t_wall": [99.0, 100.0, 101.0, 105.0, 110.0],
        "odom_m": [0, 10, 20, 30, 40],
        "v_kmh": [0, 5, 10, 20, 25],
    })

    # 2) events.jsonl con eventos *normalizados* getdata_next_limit
    ev_path = tmp_path / "events.jsonl"
    rows = [
        {
            "type": "getdata_next_limit",
            "t_wall": 100.0,
            "meta": {"to": 70.0, "dist_m": 1000.0},
        },
        {
            "type": "getdata_next_limit",
            "t_wall": 105.0,
            "meta": {"to": 70.0, "dist_m": 900.0},
        },
    ]
    with ev_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    # 3) Import de helper; si no existe en tu versión, saltar la prueba
    try:
        from tools.dist_next_limit import dist_from_getdata_probes
    except Exception:
        pytest.skip("tools.dist_next_limit.dist_from_getdata_probes no disponible en esta rama")

    s = dist_from_getdata_probes(df, ev_path)
    assert s is not None
    # Alineación esperada (merge_asof backward): 99→NaN, 100→1000, 101→1000, 105→900, 110→900
    vals = list(s.values)
    assert pd.isna(vals[0])
    assert vals[1] == pytest.approx(1000.0)
    assert vals[2] == pytest.approx(1000.0)
    assert vals[3] == pytest.approx(900.0)
    assert vals[4] == pytest.approx(900.0)
