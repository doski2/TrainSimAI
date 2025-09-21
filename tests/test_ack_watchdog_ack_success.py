import time

import pytest

from ingestion.rd_fake import FakeRailDriver
from ingestion.rd_client import RDClient


@pytest.mark.safety
def test_ack_watchdog_no_retry_on_ack(monkeypatch, tmp_path):
    """If the RD applies the value immediately, watchdog should not record retries or escalate."""
    monkeypatch.chdir(tmp_path)

    rd = FakeRailDriver()
    client = RDClient(poll_dt=0.01, control_aliases=None, ack_watchdog=True, ack_watchdog_interval=0.01)
    client.rd = rd
    client.ctrl_index_by_name = {name: idx for idx, name in rd.get_controller_list()}

    # normal set implementation: returns ack
    # shorten timeouts
    client._ack_timeout = 0.05
    client._max_retries = 3

    shim = client._make_rd()
    shim.set_controller_value("VirtualBrake", 0.5)

    # wait briefly for worker to process
    time.sleep(0.1)

    assert client._retry_counts.get("VirtualBrake", 0) == 0, "Unexpected retries when ACK present"
    assert not client._emergency_active, "Unexpected emergency when ACK present"

