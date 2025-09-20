"""
Simple script to set operation mode via `data/control_status.json`.
Usage: python scripts/set_mode.py --mode ai_autonomous --confirm
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import time

ap = argparse.ArgumentParser()
ap.add_argument("--mode", choices=["manual", "ai_assist", "ai_autonomous"], required=True)
ap.add_argument("--confirm", action="store_true")
args = ap.parse_args()

if not args.confirm:
    print("Use --confirm to actually write the mode")
    raise SystemExit(2)

Path("data").mkdir(parents=True, exist_ok=True)
Path("data/control_status.json").write_text(
    json.dumps({"mode": args.mode, "takeover": args.mode == "manual", "ts": time.time()}), encoding="utf-8"
)
print(f"Wrote mode {args.mode} to data/control_status.json")
