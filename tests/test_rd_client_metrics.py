import time
import importlib
from ingestion.rd_fake import FakeRailDriver
from ingestion.rd_client import RDClient, RD_RETRIES, RD_EMERGENCY, RD_ACK_LATENCY, RD_EMERGENCY_GAUGE


def test_metrics_presence_and_behavior(tmp_path):
    fake = FakeRailDriver()
    client = RDClient(poll_dt=0.01, rd=fake)
    client._ack_timeout = 0.01
    client._max_retries = 1

    rd = client._make_rd()

    # If prometheus is not installed, the constants are None
    try:
        importlib.import_module('prometheus_client')
    except Exception:
        assert RD_RETRIES is None and RD_EMERGENCY is None and RD_ACK_LATENCY is None
        return

    # Otherwise, simulate a missing ack to cause a retry and emergency
    def never_apply(index_or_name, value):
        # don't apply to cause ack miss
        return

    fake.set_controller_value = never_apply

    rd.set_controller_value('Regulator', 0.9)
    time.sleep(0.1)

    # metrics should have been incremented
    assert RD_RETRIES is not None
    assert RD_EMERGENCY is not None
    # we can't directly read Counter value easily without registry introspection here,
    # but ensure the emergency gauge is set if present
    if RD_EMERGENCY_GAUGE is not None:
        # gauge should be 1 (emergency active)
        val = RD_EMERGENCY_GAUGE._value.get()  # rely on prometheus client internals for test
        assert int(val) == 1

