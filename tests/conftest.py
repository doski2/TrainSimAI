import pytest

# Provide a small, safe fixture that returns the FakeRailDriver class from the
# ingestion package. Tests can use `fake_rd` or `make_client` to obtain an
# `RDClient` with the fake injected, preventing accidental construction of a
# real RailDriver in CI.
@pytest.fixture
def fake_rd():
    from ingestion.rd_fake import FakeRailDriver

    return FakeRailDriver


@pytest.fixture
def make_client(fake_rd):
    """Factory that constructs an RDClient with a FakeRailDriver instance.

    Usage in tests:
        client = make_client()
        # or with custom args: client = make_client(poll_dt=0.1, ack_watchdog=True)
    """

    def _make(**kwargs):
        from ingestion.rd_client import RDClient

        rd_inst = fake_rd()
        # ensure tests don't start the real exporter by default
        kwargs.setdefault("ack_watchdog", False)
        return RDClient(rd=rd_inst, **kwargs)

    return _make
import sys
from pathlib import Path

# Seguridad: bloquea tests 'real' si no está el entorno adecuado
import os

# pyright: reportMissingImports=false
import pytest


def pytest_runtest_setup(item):
    if "real" in getattr(item, "keywords", {}):
        if os.environ.get("RUN_RD_TESTS") != "1":
            pytest.skip("Test 'real' requiere RUN_RD_TESTS=1 (hardware activo)")


# Add repository root to sys.path so tests can import runtime/* modules
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
