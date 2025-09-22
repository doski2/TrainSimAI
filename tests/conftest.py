import sys
from pathlib import Path
import os

import pytest

from ingestion.rd_fake import FakeRailDriver


@pytest.fixture
def fake_rd():
    """Return a fresh FakeRailDriver instance for tests."""
    return FakeRailDriver()


@pytest.fixture
def make_client(fake_rd):
    """Factory that returns an RDClient with the fake driver attached."""
    from ingestion.rd_client import RDClient

    def _make(**kwargs):
        c = RDClient(**kwargs, rd=fake_rd)
        return c, fake_rd

    return _make


def pytest_runtest_setup(item):
    if "real" in getattr(item, "keywords", {}):
        if os.environ.get("RUN_RD_TESTS") != "1":
            pytest.skip("Test 'real' requiere RUN_RD_TESTS=1 (hardware activo)")


# Add repository root to sys.path so tests can import runtime/* modules
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
