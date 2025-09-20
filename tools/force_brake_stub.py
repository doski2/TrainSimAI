#!/usr/bin/env python3
"""Pequeño script para forzar llamadas al stub RD y verificar que se registran."""

from __future__ import annotations

import time
import sys
from pathlib import Path

# Ensure repo root is on path so `runtime` is importable when script run from tools/
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    # Import the stub after ensuring repo root is on sys.path
    import importlib

    stub = importlib.import_module("runtime.raildriver_stub")
    rd = getattr(stub, "rd")

    print("Forzando llamadas a rd.set_brake / rd.set_throttle 10 veces...")
    for i in range(10):
        # Alternar valores para ver cambios
        b = 0.8 if i % 2 == 0 else 0.2
        t = 0.0
        rd.set_brake(b)
        rd.set_throttle(t)
        time.sleep(0.1)
    print("Hecho")


if __name__ == "__main__":
    main()
