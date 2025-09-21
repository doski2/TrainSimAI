import time
from ingestion.rd_fake import FakeRailDriver
from ingestion.rd_client import RDClient


def test_ack_recovery_before_max_retries(monkeypatch):
    """Driver delays applying value briefly; ack appears within retries and no emergency is triggered."""
    fake = FakeRailDriver()
    client = RDClient(poll_dt=0.01)
    client.rd = fake
    client.ctrl_index_by_name = {name: idx for idx, name in fake.get_controller_list()}
    client._ack_timeout = 0.05
    client._max_retries = 3

    rd = client._make_rd()

    # Simulate delayed apply: first call stores pending, second call applies
    applied = {}
    original_set = fake.set_controller_value

    call_count = {"n": 0}

    def flaky_set(index_or_name, value):
        call_count["n"] += 1
        if call_count["n"] < 2:
            # first call: don't apply immediately
            applied[index_or_name] = value
        else:
            # second call: apply normally
            return original_set(index_or_name, value)

    fake.set_controller_value = flaky_set

    rd.set_controller_value("Regulator", 0.8)

    # allow some time for retries/acks
    time.sleep(0.2)

    assert client._emergency_active is False
    # After recovery, the fake driver should reflect the set value
    idx = client.ctrl_index_by_name.get("Regulator")
    assert idx is not None
    val = fake.get_current_controller_value(idx)
    assert abs(val - 0.8) <= 1e-3


def test_transient_driver_errors_do_not_cause_emergency(monkeypatch):
    """Driver raises on first set then recovers; should not trigger emergency if within retries."""
    fake = FakeRailDriver()
    client = RDClient(poll_dt=0.01)
    client.rd = fake
    client.ctrl_index_by_name = {name: idx for idx, name in fake.get_controller_list()}
    client._ack_timeout = 0.05
    client._max_retries = 3

    rd = client._make_rd()

    original_set = fake.set_controller_value
    calls = {"n": 0}

    def sometimes_error(index_or_name, value):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("simulated driver glitch")
        return original_set(index_or_name, value)

    fake.set_controller_value = sometimes_error

    rd.set_controller_value("Regulator", 0.5)
    time.sleep(0.2)

    assert client._emergency_active is False
    idx = client.ctrl_index_by_name.get("Regulator")
    assert idx is not None
    assert abs(fake.get_current_controller_value(idx) - 0.5) <= 1e-3
