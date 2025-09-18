# pyright: reportMissingImports=false
import os
from typing import Any, TYPE_CHECKING
if TYPE_CHECKING:
    import pytest
else:
    class _PytestShim:
        def __getattr__(self, name):
            def _decorator(*a, **k):
                def _wrap(f): return f
                return _wrap
            return _decorator
    pytest = _PytestShim()  # type: ignore

RUN_LIVE = os.environ.get("RUN_RD_TESTS") == "1"


@pytest.mark.real
@pytest.mark.skipif(not RUN_LIVE, reason="Set RUN_RD_TESTS=1 para ejecutar con RailDriver real")
def test_rd_live_snapshot():
    # Importar aquí evita errores de Pylance cuando no hay entorno/HW
    from raildriver import RailDriver
    from raildriver.events import Listener

    rd: Any = RailDriver()
    rd.setRailSimConnected(True)
    rd.setRailDriverConnected(True)
    li: Any = Listener(rd, interval=0.1)
    li.add("!LocoName")
    li.add("!Coordinates")
    snap = li.snapshot()
    assert "!LocoName" in snap
