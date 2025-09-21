import time

from typing import Tuple

from ingestion.rd_fake import FakeRailDriver
from ingestion.rd_client import RDClient


def _make_client_with_fake(tmp_path) -> Tuple[RDClient, FakeRailDriver]:
    # keep test filesystem isolated
    import os

    os.chdir(tmp_path)
    client = RDClient(poll_dt=0.01, ack_watchdog=False)
    rd = FakeRailDriver()
    client.rd = rd
    client.ctrl_index_by_name = {name: idx for idx, name in rd.get_controller_list()}
    return client, rd


def test_virtual_brake_and_engine_brake_detected(tmp_path):
    client, rd = _make_client_with_fake(tmp_path)

    common = client._common_controls()
    # Ensure VirtualBrake and VirtualEngineBrakeControl are recognized
    assert any(n in common for n in ("VirtualBrake", "VirtualEngineBrakeControl")), (
        "Expected VirtualBrake or VirtualEngineBrakeControl in common controls"
    )


def test_shim_set_brake_affects_fake_driver(tmp_path):
    client, rd = _make_client_with_fake(tmp_path)
    # Use client's shim factory which returns an object compatible with the
    # runtime expectations. The shim exposes `set_controller_value` (index/name)
    # which is safe and visible to static analyzers; calling `set_brake` was
    # previously triggering an attribute-unknown warning in static checks.
    shim = client._make_rd()

    # call shim.set_controller_value using the name to ensure resolution
    shim.set_controller_value("VirtualBrake", 1.0)
    # allow small time for any async processing (none expected here)
    time.sleep(0.02)
    # Confirm FakeRailDriver state updated
    val = rd.get_current_controller_value("VirtualBrake")
    assert abs(float(val) - 1.0) <= 1e-6, f"VirtualBrake not applied to fake driver, got {val}"

