from __future__ import annotations

from runtime.guards import RateLimiter, overspeed_guard


def test_rate_limiter_caps_delta():
    rl = RateLimiter(max_delta_per_s=1.0)
    rl.reset(0.0)
    out1 = rl.step(1.0, dt=0.1)
    assert 0.09 <= out1 <= 0.11  # ~0.1 por tick
    out2 = rl.step(1.0, dt=0.1)
    assert 0.19 <= out2 <= 0.21


def test_overspeed_guard_monotonic():
    # sin límite → 0
    assert overspeed_guard(100, None) == 0.0
    # justo por debajo del umbral
    assert overspeed_guard(101.4, 100.0, delta_kph=1.5) == 0.0
    # sobrepasa
    assert overspeed_guard(105.0, 100.0, delta_kph=1.5) > 0.0

