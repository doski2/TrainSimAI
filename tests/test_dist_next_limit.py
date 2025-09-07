from __future__ import annotations

import numpy as np
import pandas as pd

from tools.dist_next_limit import compute_distances


def test_compute_distances_synthetic():
    # t cada 1 s, velocidad 10 m/s → odom lineal
    df = pd.DataFrame({
        "t_wall": np.arange(0, 6, dtype=float),
        "v_ms": np.full(6, 10.0),
    })
    # distancias integradas: 0,10,20,30,40,50
    # Eventos en odom 25 y 50 → dist: [25,15,5,20,10,0?] para cada muestra
    events = [
        {"type": "speed_limit_change", "odom_m": 25.0, "meta": {"to": 120}},
        {"type": "speed_limit_change", "odom_m": 50.0, "meta": {"to": 100}},
    ]
    df_out, e_odom, e_next = compute_distances(df, events)
    expected = np.array([25, 15, 5, 20, 10, 0], dtype=float)
    # La última muestra no tiene siguiente evento: tratamos NaN como 0 para comparar
    assert np.allclose(
        np.nan_to_num(df_out["dist_next_limit_m"].to_numpy(), nan=0.0), expected
    )
    # next_limit_kph de los eventos proyectados
    expected_next = np.array([120, 120, 120, 100, 100, np.nan], dtype=float)
    assert np.allclose(
        np.nan_to_num(df_out["next_limit_kph"].to_numpy(), nan=-1),
        np.nan_to_num(expected_next, nan=-1),
    )
