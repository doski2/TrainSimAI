from profiles import controls as _controls


def _make_dummy_rd(names):
    """Create a lightweight object with the minimal shape to call _common_controls()."""

    class Dummy:
        def __init__(self, names):
            # emulate ctrl_index_by_name mapping used by _common_controls
            self.ctrl_index_by_name = {n: i for i, n in enumerate(names)}

    return Dummy(names)


def test_common_controls_uses_profiles_controls():
    # pick a canonical entry and ensure at least one alias is present in the names
    # e.g., 'sifa' canonical has aliases like 'Sifa' and 'SIFA'
    aliases = _controls.CONTROLS.get("sifa", [])
    assert aliases, "profiles.controls must declare 'sifa' aliases for this test"
    # choose a subset of aliases to simulate the driver's controller list
    sample = [aliases[0], "Regulator", "SpeedometerKPH"]
    rd = _make_dummy_rd(sample)
    # call the RDClient._common_controls function with rd as 'self'
    from ingestion.rd_client import RDClient
    from typing import cast

    got = RDClient._common_controls(cast(RDClient, rd))
    # ensure that at least the alias we provided is returned
    assert any(a in got for a in sample), f"expected some of {sample} in {got}"


def test_common_controls_fallback_on_missing_profiles():
    # When the driver exposes only names matched by historical heuristics,
    # _common_controls should still pick them (e.g., 'Regulator' -> Throttle)
    sample = ["Regulator", "TrainBrake"]
    rd = _make_dummy_rd(sample)
    from ingestion.rd_client import RDClient
    from typing import cast

    got = RDClient._common_controls(cast(RDClient, rd))
    assert "Regulator" in got or "TrainBrake" in got
