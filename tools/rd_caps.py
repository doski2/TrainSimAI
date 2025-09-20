from __future__ import annotations

import os
import platform
import sys
from pathlib import Path


def _ensure_raildriver_on_path() -> None:
    here = Path(__file__).resolve().parent
    candidate = here.parent / "py-raildriver-master"
    if candidate.exists():
        sys.path.insert(0, str(candidate))


_ensure_raildriver_on_path()

# Imports después de ajustar sys.path
from raildriver import RailDriver  # type: ignore  # noqa: E402
from raildriver.events import Listener  # type: ignore  # noqa: E402


def _locate_raildriver_dll() -> str | None:
    wants_64 = platform.architecture()[0] == "64bit"
    candidates: list[Path] = []
    # Overwrite via env
    env_plugins = os.environ.get("RAILWORKS_PLUGINS")
    if env_plugins:
        base = Path(env_plugins)
        candidates += [base / "RailDriver64.dll", base / "RailDriver.dll"]
    # Common Steam install paths
    common_bases = [
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\\Program Files (x86)"))
        / "Steam"
        / "steamapps"
        / "common"
        / "RailWorks"
        / "plugins",
        Path(os.environ.get("PROGRAMFILES", r"C:\\Program Files"))
        / "Steam"
        / "steamapps"
        / "common"
        / "RailWorks"
        / "plugins",
    ]
    try:
        import winreg  # type: ignore

        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
        reg_base = Path(steam_path) / "steamapps" / "common" / "RailWorks" / "plugins"
        common_bases.insert(0, reg_base)
    except Exception:
        pass
    for base in common_bases:
        candidates += [base / "RailDriver64.dll", base / "RailDriver.dll"]
    existing = [p for p in candidates if p.exists()]
    if not existing:
        return None
    if wants_64:
        for p in existing:
            if p.name.lower() == "raildriver64.dll":
                return str(p)
    return str(existing[0])


SPECIALS = [
    "!Coordinates",
    "!Heading",
    "!Gradient",
    "!FuelLevel",
    "!IsInTunnel",
    "!Time",
    "!LocoName",
]


def main() -> None:
    # Instanciar RailDriver (preferir DLL acorde a arquitectura si es posible)
    dll_path = _locate_raildriver_dll()
    rd = RailDriver(dll_location=dll_path) if dll_path else RailDriver()

    # Listener sin hilo; haremos una iteración manual para snapshot
    listener = Listener(rd, interval=0.1)
    # No es necesario subscribir para SPECIALS; el Listener las evalúa cada iteración
    listener._main_iteration()  # type: ignore[attr-defined]
    snap = dict(getattr(listener, "current_data", {}) or {})

    print("=== SPECIALS ===")
    for k in SPECIALS:
        v = snap.get(k, None)
        print(f"{k:16} -> {repr(v)}")

    print("\n=== Controllers (sample) ===")
    ctrls = list(rd.get_controller_list())
    for idx, (i, n) in enumerate(ctrls[:40]):
        try:
            mn = rd.get_min_controller_value(i)
            mx = rd.get_max_controller_value(i)
        except Exception:
            mn = mx = float("nan")
        print(f"[{i:3}] {n:32}  min={mn:8.3f} max={mx:8.3f}")
    print(f"... total {len(ctrls)} controls")


if __name__ == "__main__":
    main()
