import importlib


def test_canonicalize_variants():
    from profiles import controls

    # PZB variants with/without Hz
    assert controls.canonicalize("PZB_1000Hz") == "pzb"
    assert controls.canonicalize("PZB_1000") == "pzb"

    # Sifa variants
    assert controls.canonicalize("Sifa") == "sifa"
    assert controls.canonicalize("SIFA") == "sifa"

    # Brake aliases
    assert controls.canonicalize("VirtualBrake") == "brake"
    assert controls.canonicalize("TrainBrakeControl") == "brake"


def test_rdclient_common_controls_prefers_canonical(monkeypatch):
    # Ensure RDClient uses the canonical mapping when available
    rd_mod = importlib.import_module("ingestion.rd_client")
    # Force fake usage to avoid instantiating real drivers in CI/local
    monkeypatch.setattr(rd_mod, "USE_FAKE", True)

    client = rd_mod.RDClient(poll_dt=0.01)

    # Simulate a driver exposing a set of names (mixed variants)
    client.ctrl_index_by_name = {
        "PZB_1000Hz": 0,
        "SpeedometerKPH": 1,
        "VirtualBrake": 2,
        "Regulator": 3,
        "Throttle": 4,
    }

    chosen = client._common_controls()

    # The canonical-aware logic should include these driver names
    assert "PZB_1000Hz" in chosen
    assert "VirtualBrake" in chosen
    # either regulator or throttle should be present as throttle candidate
    assert any(x in chosen for x in ("Regulator", "Throttle"))
