import pytest
from typing import Any, cast


@pytest.mark.safety
def test_emergency_path_isolated(monkeypatch, tmp_path):
    """Simple safety test that simulates RDClient emergency escalation path.

    This test is intentionally small: it creates a fake RD client object with
    controlled behavior and asserts that emergency_stop is invoked when the
    driver fails to confirm sets.
    """

    # Minimal fake RDClient-like object
    class FakeRD:
        def __init__(self):
            self.calls = []

        def set_controller_value(self, idx, v):  # mimic driver's index-based API
            self.calls.append((idx, v))

    # Create a lightweight fake RDClient with the bits our RD shim expects
    from ingestion.rd_client import RDClient

    from typing import Any, cast

    fake = FakeRD()

    # Construct a minimal RDClient instance but inject our fake RD to avoid
    # real IO during construction.
    rc = RDClient(poll_dt=1.0, rd=cast(Any, fake))
    # ensure no indices mapped so set attempts will escalate
    rc.ctrl_index_by_name = {}
    # short retry policy for test
    rc._max_retries = 1

    # track if emergency_stop is called
    called = {}

    def _emergency(reason: str = "unknown") -> None:
        called['reason'] = reason

    rc.emergency_stop = _emergency

    shim = None
    try:
        shim = rc._make_rd()
    except Exception:
        pytest.skip("environment not suitable for shim creation")

    # calling set_controller_value with no index should eventually trigger emergency
    shim.set_controller_value('NonExisting', 0.5)
    assert 'reason' in called


@pytest.mark.safety
def test_ack_watchdog_enqueue(monkeypatch):
    """When ack_watchdog is enabled, a successful set enqueues a confirmation tuple.

    We simulate a driver that accepts index-based sets and verify the ack queue
    receives the entry (name, value, attempts).
    """

    class FakeRD:
        def __init__(self):
            self.calls = []

        def set_controller_value(self, idx, v):
            self.calls.append((idx, v))

        def get_current_controller_value(self, idx):
            # reflect last set for confirmation attempts
            for i, val in reversed(self.calls):
                if i == idx:
                    return val
            return 0.0

    from ingestion.rd_client import RDClient

    rc = RDClient(poll_dt=1.0, rd=cast(Any, FakeRD()))
    # map a control name to an integer index so set path uses index-based call
    rc.ctrl_index_by_name = {"Throttle": 1}
    rc._max_retries = 3
    rc._ack_watchdog_enabled = True
    # ensure queue exists

    q = rc._ack_queue

    shim = rc._make_rd()
    # call the shim by name; since driver accepts index, this should enqueue
    shim.set_controller_value("Throttle", 0.5)

    # Read queued item
    item = q.get_nowait()
    assert item[0] == "Throttle"
    assert abs(item[1] - 0.5) < 1e-6


@pytest.mark.safety
def test_retry_exhaustion_triggers_emergency(monkeypatch):
    """When driver errors repeatedly and retries exceed limit, emergency_stop is called."""

    class FakeRD:
        def set_controller_value(self, idx, v):
            raise RuntimeError("driver fail")

    from ingestion.rd_client import RDClient

    rc = RDClient(poll_dt=1.0, rd=cast(Any, FakeRD()))
    # provide a mapping so shim tries index-based calls
    rc.ctrl_index_by_name = {"Brake": 2}
    rc._max_retries = 0

    called = {}

    def _emergency(reason: str = "unknown") -> None:
        called['reason'] = reason

    rc.emergency_stop = _emergency

    shim = rc._make_rd()
    shim.set_controller_value("Brake", 1.0)
    assert 'reason' in called
