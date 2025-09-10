from __future__ import annotations
from runtime.control_loop import _to_float_loose
import math

def test_to_float_loose_thousands_and_decimal():
    assert _to_float_loose("1.234.567,89") == 1234567.89
    assert _to_float_loose("-2,29E+10") == -2.29e10
    assert math.isnan(_to_float_loose(""))
    assert math.isnan(_to_float_loose("nan"))
    # Muchos puntos (miles): se eliminan
    v = _to_float_loose("17.574.600.689.769.800")
    assert isinstance(v, float)
