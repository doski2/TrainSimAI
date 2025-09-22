from profiles.controls import canonicalize


def test_canonicalize_known_aliases():
    assert canonicalize("brake") == "brake"
    assert canonicalize("BrakeCmd") == "brake"
    assert canonicalize("VirtualBrake") == "brake"
    assert canonicalize("throttle") == "throttle"


def test_canonicalize_unknown():
    assert canonicalize("nonexistent_control") is None
