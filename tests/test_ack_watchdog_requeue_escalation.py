import time

import pytest

@pytest.mark.safety
def test_ack_watchdog_retries_and_escalates(monkeypatch, tmp_path, make_client):
    """Ensure the ack watchdog requeues attempts, records retries and escalates to emergency
    when the fake driver never applies the value.
    """
    # NOTE: test created to validate ack-watchdog behaviour (no-op comment to allow PR creation)
    monkeypatch.chdir(tmp_path)

    client, rd = make_client(poll_dt=0.01, control_aliases=None, ack_watchdog=True, ack_watchdog_interval=0.01)

    # make driver ignore sets (no ack)
    def _no_op(index_or_name, value):
        return None

    rd.set_controller_value = _no_op

    # shorten timeouts for test speed
    client._ack_timeout = 0.02
    client._max_retries = 2

    shim = client._make_rd()

    # optimistic set; watchdog will enqueue and process in background
    shim.set_controller_value("VirtualBrake", 1.0)

    # wait until either emergency is active or timeout
    deadline = time.time() + 3.0
    while time.time() < deadline:
        if client._emergency_active:
            break
        # also break early if retry count grows (worker is active)
        if client._retry_counts.get("VirtualBrake", 0) > 0:
            # wait a bit more for eventual escalation
            time.sleep(0.05)
        time.sleep(0.02)

    assert client._retry_counts.get("VirtualBrake", 0) >= 1, "watchdog did not record retries"
    assert client._emergency_active, "watchdog did not escalate to emergency after retries"
