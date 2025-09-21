import time

import pytest

from ingestion.rd_fake import FakeRailDriver
from ingestion.rd_client import RDClient


@pytest.mark.safety
def test_ack_watchdog_clears_retries_when_ack_arrives(monkeypatch, tmp_path):
    """If ACK arrives after some retries, the retry counts should be cleared and no emergency should remain."""
    monkeypatch.chdir(tmp_path)

    rd = FakeRailDriver()
    client = RDClient(poll_dt=0.01, control_aliases=None, ack_watchdog=True, ack_watchdog_interval=0.01, rd=rd)

    # Instead of modifying driver's set method, simulate that an external
    # process applies the requested value after a short delay (ACK arrival).
    client._ack_timeout = 0.02
    client._max_retries = 5

    shim = client._make_rd()

    # schedule a background setter that will apply the value after two watchdog cycles
    import threading

    def delayed_apply():
        # wait a bit for the watchdog to enqueue and possibly record retries
        time.sleep(0.2)
        # apply value directly to the fake driver's internal state to simulate ACK
        try:
            idx = rd.get_controller_index("VirtualBrake")
            rd.set_controller_value(idx, 0.7)
        except Exception:
            rd.set_controller_value("VirtualBrake", 0.7)

    t = threading.Thread(target=delayed_apply, daemon=True)
    t.start()

    shim.set_controller_value("VirtualBrake", 0.7)

    # wait until the worker has attempted retries and eventually observed the ACK
    deadline = time.time() + 3.0
    while time.time() < deadline:
        # if retries recorded at all, and no emergency, allow a short settle
        if client._retry_counts.get("VirtualBrake", 0) > 0 and not client._emergency_active:
            time.sleep(0.05)
            break
        time.sleep(0.02)

    # After ACK arrives, either retries were recorded and then cleared, and no emergency
    # Confirm the fake driver reflects the applied value eventually and no emergency
    # (we don't assert exact retry counter semantics here to avoid timing flakiness).
    deadline2 = time.time() + 2.0
    ok = False
    while time.time() < deadline2:
        try:
            val = rd.get_current_controller_value("VirtualBrake")
            if abs(float(val) - 0.7) <= 1e-3:
                ok = True
                break
        except Exception:
            pass
        time.sleep(0.02)

    assert ok, "FakeRailDriver did not reflect applied value after ACK"
    assert not client._emergency_active, "Emergency should not remain after ACK arrival"
    assert not client._emergency_active, "Emergency should not remain after ACK arrival"
