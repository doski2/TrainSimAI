from __future__ import annotations
from typing import Dict, Any


# Convierte eventos crudos (LUA o heurísticas) a un modelo estable
# type: "speed_limit_change" | "stop_begin" | "stop_end" | "marker_pass" | "custom"


def normalize(evt: dict) -> dict:
    t = evt.get("type")
    out = {"t_ingame": evt.get("time"), "lat": evt.get("lat"), "lon": evt.get("lon")}
    if t == "speed_limit_change":
        out.update({
            "type": "speed_limit_change",
            "limit_prev_kmh": evt.get("prev"),
            "limit_next_kmh": evt.get("next"),
            "dist_est_m": evt.get("dist"),
        })
    elif t == "limit_reached":
        out.update({
            "type": "limit_reached",
            "limit_kmh": evt.get("limit_kmh"),
            "dist_m_travelled": evt.get("dist_m_travelled"),
            "odom_m": evt.get("odom_m"),
        })
    elif t in ("stop_begin", "stop_end"):
        out.update({"type": t, "station": evt.get("station")})
    elif t == "marker_pass":
        out.update({"type": t, "marker": evt.get("name")})
    else:
        out.update({"type": "custom", "payload": evt})
    return out
