from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime
import json


_LOG_PATH = Path(os.environ.get("TSC_RD_LOG", "data/rd_send.log"))
_DEBUG = os.environ.get("TSC_RD_DEBUG", "0") in ("1", "true", "True")


def _ensure_log_dir():
    try:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def _append_log(action: str, value) -> None:
    _ensure_log_dir()
    try:
        ts = datetime.utcnow().isoformat() + "Z"
        entry = {"ts": ts, "action": action, "value": value}
        with _LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        # best-effort only
        pass


class RDStub:
    def setTrainBrake(self, v: float) -> None:
        msg = f"[RDStub] setTrainBrake({v})"
        if _DEBUG:
            print(msg)
        _append_log("setTrainBrake", v)
        # best-effort: write an ack file so external controllers can detect application
        try:
            p = Path("data/rd_ack.json")
            p.parent.mkdir(parents=True, exist_ok=True)
            entry = {"ts": datetime.utcnow().timestamp(), "value": float(v)}
            tmp = p.with_suffix('.tmp')
            tmp.write_text(json.dumps(entry), encoding='utf-8')
            tmp.replace(p)
        except Exception:
            pass

    def set_brake(self, v: float) -> None:
        msg = f"[RDStub] set_brake({v})"
        if _DEBUG:
            print(msg)
        _append_log("set_brake", v)
        # best-effort ack file for ControlLoop to observe
        try:
            p = Path("data/rd_ack.json")
            p.parent.mkdir(parents=True, exist_ok=True)
            entry = {"ts": datetime.utcnow().timestamp(), "value": float(v)}
            tmp = p.with_suffix('.tmp')
            tmp.write_text(json.dumps(entry), encoding='utf-8')
            tmp.replace(p)
        except Exception:
            pass

    def set_throttle(self, v: float) -> None:
        msg = f"[RDStub] set_throttle({v})"
        if _DEBUG:
            print(msg)
        _append_log("set_throttle", v)


rd = RDStub()
