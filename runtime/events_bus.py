from __future__ import annotations
from typing import Dict, Any


# Convierte eventos crudos (LUA o heurísticas) a un modelo estable
# type: "speed_limit_change" | "stop_begin" | "stop_end" | "marker_pass" | "custom"


def normalize(evt: Dict[str, Any]) -> Dict[str, Any]:
    t = evt.get("type")
    base = {"t_ingame": evt.get("time"), "lat": evt.get("lat"), "lon": evt.get("lon")}
    if t == "speed_limit_change":
        base.update({
            "type": t,
            "limit_prev_kmh": evt.get("prev"),
            "limit_next_kmh": evt.get("next"),
            "dist_est_m": evt.get("dist"),
        })
    elif t in ("stop_begin", "stop_end"):
        base.update({"type": t, "station": evt.get("station")})
    elif t == "marker_pass":
        base.update({"type": t, "marker": evt.get("name")})
    else:
        base.update({"type": "custom", "payload": evt})
    return base

