import time
import threading


def test_watchdog_confirms_before_max_retries(make_client):
    # Use factory to get client with fake RD; simulate delayed acknowledgement
    client = make_client(poll_dt=0.01, control_aliases=None, ack_watchdog=True, ack_watchdog_interval=0.01)
    rd = client.rd
    # ensure index mapping is present for VirtualBrake
    client.ctrl_index_by_name = {name: idx for idx, name in rd.get_controller_list()}

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

    t = threading.Thread(target=delayed_apply, daemon=True)
    t.start()

    shim.set_controller_value("VirtualBrake", 1.0)

    # wait longer than delayed apply + worker interval
    time.sleep(0.2)

    # ensure no emergency was triggered
    assert not client._emergency_active

    # tidy
    client.shutdown()


def test_watchdog_escalates_on_missing_ack(make_client):
    client = make_client(poll_dt=0.01, control_aliases=None, ack_watchdog=True, ack_watchdog_interval=0.01)
    rd = client.rd
    shim = client._make_rd()

    # Do NOT apply value in driver; watchdog should escalate after retries
    client._ack_timeout = 0.05
    client._max_retries = 1
    rd.set_controller_value = lambda idx, v: None
    shim.set_controller_value("VirtualBrake", 1.0)

    wait_time = (client._max_retries + 1) * client._ack_timeout + 0.2
    time.sleep(wait_time)

    assert client._emergency_active

    client.shutdown()
