import pytest


def test_normalize_getdata_next_limit_maps_meta():
    # Import on demand to avoid import cost in other tests
    from runtime.events_bus import normalize

    e = {
        "type": "getdata_next_limit",
        "kph": 70.0,
        "dist_m": 3601.0,
        "t_wall": 123.0,
        "odom_m": 42.0,
    }
    out = normalize(e)
    assert out["type"] == "getdata_next_limit"
    assert out["t_wall"] == 123.0
    assert out["odom_m"] == 42.0
    assert "meta" in out
    assert out["meta"]["to"] == pytest.approx(70.0)
    assert out["meta"]["dist_m"] == pytest.approx(3601.0)

