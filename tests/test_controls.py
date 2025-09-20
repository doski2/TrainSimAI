from profiles import controls


def test_canonicalize_basic():
    assert controls.canonicalize("brake") == "brake"
    assert controls.canonicalize("BrakeCmd") == "brake"
    assert controls.canonicalize("throttle") == "throttle"
    assert controls.canonicalize("unknown_control") is None


def test_canonicalize_normalization():
    # variants with hyphens/spaces/underscore and different case
    assert controls.canonicalize("brake-cmd") == "brake"
    assert controls.canonicalize(" Brake Cmd ") == "brake"
    assert controls.canonicalize("THROTTLE_cmd") == "throttle"
