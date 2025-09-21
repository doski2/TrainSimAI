"""Centralized control names and aliases.

This module centralizes the mapping of control canonical names to known
aliases used across profiles and the RD client. Import this from
`ingestion.rd_client` and other places that need to recognise control
names.

Keep this list conservative and add aliases as needed when adding new
vehicle profiles.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Dict, Iterable, List

# canonical_name -> list of aliases (including canonical)
CONTROLS: Dict[str, List[str]] = {
    "brake": [
        "brake",
        "brake_cmd",
        "brakedemand",
        "brake_demand",
        "BrakeCmd",
        "TrainBrake",
        "TrainBrakeControl",
        "VirtualBrake",
    ],
    "throttle": [
        "throttle",
        "power",
        "traction",
        "throttle_cmd",
        "Regulator",
        "Throttle",
    ],
    "speed_setpoint": ["speed_setpoint", "target_speed", "v_set"],

    # Safety systems and driver vigilance
    "sifa": [
        "sifa",
        "Sifa",
        "SIFA",
        "SifaReset",
        "SifaLight",
        "SifaAlarm",
        "VigilEnable",
    ],

    # PZB/inductive train protection variants (with/without Hz suffixes)
    "pzb": [
        "PZB_1000Hz",
        "PZB_1000",
        "PZB_500Hz",
        "PZB_500",
        "PZB_85",
        "PZB_70",
        "PZB_55",
        "PZB_40",
        "PZB_B40",
        "PZB_Warning",
        "PZB_Emergency",
        "PZB_Restriction",
    ],

    # Engine/locomotive brake variants
    "engine_brake": [
        "VirtualEngineBrakeControl",
        "LocoBrakeControl",
        "EngineBrake",
        "DynamicBrake",
    ],

    # Speedometer / odometry readings
    "speedometer": [
        "SpeedometerKPH",
        "SpeedometerMPH",
        "Speedometer",
    ],
}


_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


def _normalize(s: str) -> str:
    """Normalize a control name for robust matching.

    - lowercases
    - replaces non-alphanumerics with underscore
    - strips leading/trailing underscores
    """
    if not s:
        return ""
    return _NORMALIZE_RE.sub("_", s.strip().lower()).strip("_")


@lru_cache(maxsize=2048)
def canonicalize(name: str) -> str | None:
    """Return canonical control for `name`, normalizing and using a cache.

    Returns None when the name is unknown.
    """
    n = _normalize(name)
    for canon, aliases in CONTROLS.items():
        for a in aliases:
            if n == _normalize(a):
                return canon
    return None


def all_aliases() -> Iterable[str]:
    """Yield every known alias (lowercased)."""
    for aliases in CONTROLS.values():
        for a in aliases:
            yield a.lower()


__all__ = ["CONTROLS", "canonicalize", "all_aliases"]
