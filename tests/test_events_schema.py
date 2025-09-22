from __future__ import annotations

import json
import os

import pytest

EVENTS = os.path.join("data", "events", "events.jsonl")


@pytest.mark.skipif(not os.path.exists(EVENTS), reason="no events.jsonl yet")
def test_events_min_schema():
    ok, total = 0, 0
    with open(EVENTS, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            total += 1
            obj = json.loads(line)
            assert "type" in obj, "Cada evento debe llevar 'type'"
            assert (
                ("t_wall" in obj) or ("t_game" in obj) or ("t_ingame" in obj)
            ), "Debe incluir tiempo de referencia (t_wall | t_game | t_ingame)"
            ok += 1
    assert ok == total and total > 0, "Eventos válidos y no vacíos"
