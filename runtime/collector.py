from __future__ import annotations

import json
import os
import time

from ingestion.rd_client import RDClient
from ingestion.lua_eventbus import LuaEventBus
from runtime.csv_logger import CsvLogger
from runtime.events_bus import normalize


CSV_PATH = os.path.join("data", "runs", "run.csv")
EVT_PATH = os.path.join("data", "events", "events.jsonl")
LUA_BUS = os.path.join("data", "lua_eventbus.jsonl")  # ajusta ruta si usas otra


def run(poll_hz: float = 10.0) -> None:
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(EVT_PATH), exist_ok=True)

    rd = RDClient(poll_hz=poll_hz)
    csvlog = CsvLogger(CSV_PATH)
    bus = LuaEventBus(LUA_BUS)

    gen = rd.stream()
    while True:
        row = next(gen)
        row["t_wall"] = time.time()
        csvlog.write_row(row)

        # drenar uno o varios eventos LUA si los hay
        for _ in range(10):
            evt = bus.poll()
            if not evt:
                break
            nrm = normalize(evt)
            with open(EVT_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(nrm, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    run(10.0)

