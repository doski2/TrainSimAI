import pandas as pd
from tools.validate_kpi import compute_kpis

def make_df():
    # Segmento 1: aprox a 80 kph, dist 100->0 sin bumps
    d1 = pd.DataFrame({
        "v_kmh": [83,82,81,80,79,80],
        "next_limit_kph": [80]*6,
        "dist_next_limit_m": [100,60,30,10,5,0],
    })
    # Segmento 2: aprox a 60 kph, con un bump de +3 m
    d2 = pd.DataFrame({
        "v_kmh": [64,63,61,60,60],
        "next_limit_kph": [60]*5,
        "dist_next_limit_m": [70,40,20,23,5],  # bump 20->23 (>2)
    })
    return pd.concat([d1,d2], ignore_index=True)

def test_kpis_basic():
    df = make_df()
    k = compute_kpis(df)
    assert k["arrivals"] >= 2
    assert 0 <= k["arrivals_ok"] <= 1
    # hay un bump en el segundo segmento
    assert k["monotonicity_bumps"] == 1
    # margen medio último 50 m existe numéricamente
    assert isinstance(k["mean_margin_last50_kph"], float)
