from __future__ import annotations

import copy
from typing import Any, Dict

# Normaliza eventos crudos (LUA o heurísticas) a un modelo estable v1


def _flatten_lua_payload(e: Dict[str, Any]) -> Dict[str, Any]:
    """
    Si viene como {"type":"custom", "payload":{"type":"..."}}, lo aplanamos.
    Conserva campos sellados por el collector (p.ej., odom_m/t_wall).
    """
    if str(e.get("type")) == "custom":
        payload = e.get("payload")
        if isinstance(payload, dict) and "type" in payload:
            merged = copy.deepcopy(e)
            merged.pop("payload", None)
            for k, v in payload.items():
                if k in ("t_wall", "odom_m"):
                    continue
                merged[k] = v
            return merged
    return e


def normalize(evt: Dict[str, Any]) -> Dict[str, Any]:
    """
    Esquema destino (retrocompatible con consumidores actuales):
      - t_ingame: float|None (acepta time/t_ingame/t_game_h de origen)
      - lat/lon: float|None
      - speed_limit_change: type, limit_prev_kmh, limit_next_kmh, dist_est_m
      - limit_reached: type, limit_kmh, dist_m_travelled, odom_m
      - stop_begin/stop_end: type, station
      - marker_pass: type, marker
      - otros: type="custom", payload=evento original aplanado
    """
    e = _flatten_lua_payload(dict(evt))
    etype = str(e.get("type") or "custom")

    out: Dict[str, Any] = {
        "type": etype,
        "t_ingame": e.get("time") or e.get("t_ingame") or e.get("t_game_h"),
        "lat": e.get("lat"),
        "lon": e.get("lon"),
        "odom_m": e.get("odom_m"),
        "t_wall": e.get("t_wall"),
        "meta": {},
        "raw": e,
    }

    if etype == "speed_limit_change":
        out.update(
            {
                "type": "speed_limit_change",
                "limit_prev_kmh": e.get("prev"),
                "limit_next_kmh": e.get("next"),
                "dist_est_m": e.get("dist"),
            }
        )
        prev_v = e.get("prev") or (e.get("meta") or {}).get("from") or e.get("from")
        next_v = e.get("next") or (e.get("meta") or {}).get("to") or e.get("to")
        if prev_v is not None:
            out["meta"]["from"] = float(prev_v)
        if next_v is not None:
            out["meta"]["to"] = float(next_v)
    elif etype == "limit_reached":
        out.update(
            {
                "type": "limit_reached",
                "limit_kmh": e.get("limit_kmh"),
                "dist_m_travelled": e.get("dist_m_travelled"),
                "odom_m": e.get("odom_m"),
            }
        )
    elif etype == "getdata_next_limit":
        # Probe desde GetData.txt con próximo límite y distancia
        out.update(
            {
                "type": "getdata_next_limit",
                "limit_next_kmh": e.get("kph"),
                "dist_est_m": e.get("dist_m"),
            }
        )
        # Añade meta.to/meta.dist_m para consumidores
        try:
            kph = e.get("kph")
            dist = e.get("dist_m")
            if kph is not None:
                out["meta"]["to"] = float(kph)
            if dist is not None:
                out["meta"]["dist_m"] = float(dist)
        except Exception:
            pass
    elif etype in ("stop_begin", "stop_end"):
        out.update({"station": e.get("station")})
    elif etype == "marker_pass":
        out.update({"marker": e.get("name")})

    return out
