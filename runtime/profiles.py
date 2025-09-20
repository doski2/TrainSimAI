from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Optional, Dict, Any

from runtime.braking_v0 import BrakingConfig


def load_braking_profile(path: str | Path, base: Optional[BrakingConfig] = None) -> BrakingConfig:
    """
    Carga parámetros de frenada desde un JSON.
    Estructura esperada:
    {
      "braking_v0": {
        "margin_kph": 3.0,
        "max_service_decel": 0.7,
        "reaction_time_s": 0.6,
        "coast_band_kph": 1.0,
        "min_target_kph": 5.0
      }
    }
    Si el JSON está “plano”, también funciona (usa las mismas claves).
    """
    cfg = base or BrakingConfig()
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        obj: Dict[str, Any] = json.load(f)

    data = obj.get("braking_v0") or obj
    # Solo aplicamos claves conocidas; el resto se ignora sin romper.
    keys = (
        "margin_kph",
        "max_service_decel",
        "reaction_time_s",
        "min_target_kph",
        "coast_band_kph",
    )
    vals = {k: float(data[k]) for k in keys if k in data}
    return replace(cfg, **vals)


def load_profile_extras(path: str | Path) -> dict:
    """Extras del perfil (por ahora: ruta CSV de curva ERA)."""
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        obj = json.load(f)
    data = obj.get("braking_v0") or obj
    extras: Dict[str, Any] = {}
    if "era_curve_csv" in obj:
        extras["era_curve_csv"] = obj["era_curve_csv"]
    elif isinstance(data, dict) and "era_curve_csv" in data:
        extras["era_curve_csv"] = data["era_curve_csv"]
    # incluir bloque 'braking' si existe (nombres y estructura pueden variar)
    if "braking" in obj and isinstance(obj["braking"], dict):
        extras["braking"] = obj["braking"]
    elif isinstance(data, dict) and "braking" in data and isinstance(data["braking"], dict):
        extras["braking"] = data["braking"]
    return extras


__all__ = ["load_braking_profile", "load_profile_extras"]
