from runtime.events_bus import normalize


def test_normalize_speed_limit():
    n = normalize({"type": "speed_limit_change", "prev": 120, "next": 80, "time": 1.5})
    assert n["type"] == "speed_limit_change"
    assert n["limit_prev_kmh"] == 120 and n["limit_next_kmh"] == 80
    assert "t_ingame" in n


def test_normalize_marker():
    n = normalize({"type": "marker_pass", "name": "Anden 1", "time": 2.0})
    assert n["type"] == "marker_pass"
    assert n["marker"] == "Anden 1"


def test_normalize_stop():
    n = normalize({"type": "stop_begin", "station": "X", "time": 3.0})
    assert n["type"] in ("stop_begin", "stop_end")
    assert n["station"] == "X"
