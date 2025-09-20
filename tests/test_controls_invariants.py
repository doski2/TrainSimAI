from profiles import controls


def test_aliases_map_uniquely():
    # Build reverse map alias -> canonical (normalized)
    rev = {}
    for canon, aliases in controls.CONTROLS.items():
        for a in aliases:
            key = a.lower()
            if key in rev:
                # allowed only if it points to the same canonical
                assert rev[key] == canon, (
                    f"alias {a} appears in multiple canonicals ({rev[key]} vs {canon})"
                )
            else:
                rev[key] = canon


def test_canonicalize_all_aliases():
    for canon, aliases in controls.CONTROLS.items():
        for a in aliases:
            got = controls.canonicalize(a)
            assert got == canon, f"canonicalize({a!r}) -> {got!r}, expected {canon!r}"
