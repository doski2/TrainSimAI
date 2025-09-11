from __future__ import annotations
from runtime.guards import RateLimiter, overspeed_guard


def test_rate_limiter_basic():
    rl = RateLimiter(max_delta_per_s=1.0)
    rl.reset(0.0)
    out = [rl.step(1.0, dt=0.1) for _ in range(5)]
    # ~0.1, 0.2, 0.3 ...
    assert 0.09 <= out[0] <= 0.11
    assert 0.49 <= out[-1] <= 0.51


def test_overspeed_guard_aggressive():
    # A 3 km/h por encima del (limite + delta), debe dar freno > 0
    br = overspeed_guard(103.0, 100.0, delta_kph=0.8)
    assert br > 0.0
