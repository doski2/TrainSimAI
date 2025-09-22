import time


def test_watchdog_confirms_before_max_retries(monkeypatch, tmp_path, make_client):
    # Use fake driver; simulate delayed acknowledgement by applying the value after some delay
    client, rd = make_client(poll_dt=0.01, control_aliases=None, ack_watchdog=True, ack_watchdog_interval=0.01)

    shim = client._make_rd()

    # simulate driver ignoring immediate set and applying after 0.05s
    orig_set = rd.set_controller_value

    def no_op_set(idx, value):
        # ignore immediate sets
        return None

    rd.set_controller_value = no_op_set

    def delayed_apply():
        time.sleep(0.05)
        idx = client.ctrl_index_by_name.get("VirtualBrake")
        if idx is not None:
            orig_set(idx, 1.0)

    import threading

    t = threading.Thread(target=delayed_apply, daemon=True)
    t.start()

    # call set_controller_value optimistically; watchdog should confirm it later and not escalate
    shim.set_controller_value("VirtualBrake", 1.0)

    # wait longer than delayed apply + worker interval
    time.sleep(0.2)

    assert not client._emergency_active
    client.shutdown()


def test_watchdog_escalates_on_missing_ack(monkeypatch, make_client):
    client, rd = make_client(poll_dt=0.01, control_aliases=None, ack_watchdog=True, ack_watchdog_interval=0.01)
    shim = client._make_rd()

    # Do NOT apply value in driver; watchdog should escalate after retries
    # shorten ack timeout and retries for test speed/ determinism
    client._ack_timeout = 0.05
    client._max_retries = 1
    # Make driver ignore sets (no ack)
    rd.set_controller_value = lambda idx, v: None
    shim.set_controller_value("VirtualBrake", 1.0)

    # wait sufficient time for retries to exhaust (based on ack_timeout and max_retries)
    wait_time = (client._max_retries + 1) * client._ack_timeout + 0.2
    time.sleep(wait_time)

    assert client._emergency_active
    client.shutdown()
