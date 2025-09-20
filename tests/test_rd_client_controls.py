from ingestion import rd_client


class DummyRD:
    def __init__(self):
        self._vals = {}

    def set_controller_value(self, idx, val):
        # store for inspection
        self._vals[idx] = val


class DummyClient(rd_client.RDClient):
    def __init__(self, ctrl_index_by_name):
        # avoid full init; set minimal attributes used by _make_rd
        self.ctrl_index_by_name = dict(ctrl_index_by_name)
        self.rd = DummyRD()


def test_make_rd_resolves_indices():
    # Simulate a loco where brake control is 'TrainBrake' at index 5 and
    # throttle is 'Regulator' at index 2
    idx_map = {"TrainBrake": 5, "Regulator": 2}
    cli = DummyClient(idx_map)

    # monkeypatch RDClient constructor used inside _make_rd
    original_rdclient = rd_client.RDClient
    try:
        rd_client.RDClient = lambda *a, **k: cli  # type: ignore
        shim = rd_client._make_rd()
        # call shim methods to set values
        shim.set_brake(0.7)
        shim.set_throttle(0.3)
        # check that DummyRD stored values at expected indices
        assert cli.rd._vals.get(5) == 0.7
        assert cli.rd._vals.get(2) == 0.3
    finally:
        rd_client.RDClient = original_rdclient


def test_make_rd_uses_injected_control_aliases():
    # Create a client where the controller names are 'MyBrake' and 'MyThrottle'
    idx_map = {"MyBrake": 9, "MyThrottle": 3}
    cli = DummyClient(idx_map)
    # Inject mapping: canonical -> aliases
    cli._control_aliases = {"brake": ["MyBrake"], "throttle": ["MyThrottle"]}

    original_rdclient = rd_client.RDClient
    try:
        rd_client.RDClient = lambda *a, **k: cli  # type: ignore
        shim = rd_client._make_rd()
        shim.set_brake(0.5)
        shim.set_throttle(0.25)
        assert cli.rd._vals.get(9) == 0.5
        assert cli.rd._vals.get(3) == 0.25
    finally:
        rd_client.RDClient = original_rdclient
