from __future__ import annotations
import math
from runtime.control_loop import _to_float_loose


def test_to_float_loose():
    # miles con puntos y coma decimal
    assert _to_float_loose("1.234.567,89") == 1234567.89
    # notación científica con coma decimal
    assert _to_float_loose("-2,29E+10") == -2.29e10
    # cadena vacía y 'nan' devuelven NaN
    assert math.isnan(_to_float_loose(""))
    assert math.isnan(_to_float_loose("nan"))
    # muchos puntos (miles): se eliminan y devuelve float
    v = _to_float_loose("17.574.600.689.769.800")
    assert isinstance(v, float)
