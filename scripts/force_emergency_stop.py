"""
Force an emergency stop by setting the takeover flag and reason in data/control_status.json
Usage: python scripts/force_emergency_stop.py --reason "manual stop"
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--reason", default="manual_emergency")
args = ap.parse_args()

Path("data").mkdir(parents=True, exist_ok=True)
Path("data/control_status.json").write_text(
    json.dumps(
        {"mode": "manual", "takeover": True, "reason": args.reason, "ts": time.time()}
    ),
    encoding="utf-8",
)
print("Emergency stop requested (written to data/control_status.json)")
