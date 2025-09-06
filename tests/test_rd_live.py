import os
from typing import Any
import pytest

RUN_LIVE = os.environ.get("RUN_RD_TESTS") == "1"


@pytest.mark.skipif(not RUN_LIVE, reason="Set RUN_RD_TESTS=1 para ejecutar con RailDriver real")
def test_rd_live_snapshot():
    from raildriver import RailDriver
    from raildriver.events import Listener

    rd: Any = RailDriver()
    rd.setRailSimConnected(True)            # type: ignore[attr-defined]
    rd.setRailDriverConnected(True)         # type: ignore[attr-defined]
    li: Any = Listener(rd, interval=0.1)    # type: ignore[call-arg]
    li.add("!LocoName")
    li.add("!Coordinates")
    snap = li.snapshot()
    assert "!LocoName" in snap
