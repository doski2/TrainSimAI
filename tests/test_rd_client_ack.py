import time
import json
def test_ack_and_emergency_on_missing_ack(tmp_path, monkeypatch, make_client):
    """Simulate a driver that delays applying controller writes so ack fails and triggers emergency_stop."""
    # Create fake driver with controllable delay
    client, fake = make_client(poll_dt=0.01, control_aliases=None)
    # set very small ack timeout and max_retries=1 to trigger quickly
    client._ack_timeout = 0.02
    client._max_retries = 1

    rd = client._make_rd()

    # Monkeypatch fake to delay applying values: override set_controller_value to store but not apply
    applied = {}

    original_set = fake.set_controller_value

    def delayed_set(index_or_name, value):
        # store but don't update current value until later
        applied[index_or_name] = value

    fake.set_controller_value = delayed_set

    # Call set via shim; since fake never applies, ack should fail and emergency activated
    rd.set_controller_value("Throttle", 0.7)

    # wait a bit for retries and emergency to run
    time.sleep(0.1)

    # emergency flag should be set
    assert client._emergency_active is True

    # Now restore original behavior and ensure we can still set after emergency (should not if emergency latches)
    fake.set_controller_value = original_set
    # Try setting again; should be no-op because emergency latched
    rd.set_controller_value("Throttle", 0.2)
    assert client._emergency_active is True

    # Check control_status.json was written
    # The RDClient writes to data/control_status.json in working dir; ensure file exists
    import os

    assert os.path.exists("data/control_status.json")
    with open("data/control_status.json", "r", encoding="utf-8") as fh:
        j = json.load(fh)
    assert j.get("mode") == "manual"
    assert j.get("takeover") is True
