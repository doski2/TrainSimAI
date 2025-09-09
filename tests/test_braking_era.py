from __future__ import annotations
from pathlib import Path
from runtime.braking_era import EraCurve


def test_era_distance_monotonic(tmp_path: Path):
    # Curva constante A=0.7 -> debe parecerse a modelo constante
    p = tmp_path / "curve.csv"
    p.write_text("speed_kph,decel_service_mps2\n0,0.7\n200,0.7\n", encoding="utf-8")
    curve = EraCurve.from_csv(p)
    d_far = curve.braking_distance(120.0, 80.0)
    d_near = curve.braking_distance(90.0, 80.0)
    assert d_far > d_near
