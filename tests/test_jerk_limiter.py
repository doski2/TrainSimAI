from __future__ import annotations
from runtime.guards import JerkBrakeLimiter

def test_jerk_limits_rate_and_output():
    jl = JerkBrakeLimiter(max_rate_per_s=1.0, max_jerk_per_s2=2.0)
    jl.reset(0.0)
    y = 0.0
    dt = 0.1
    # primer paso: no alcanza 1.0 de golpe
    y = jl.step(1.0, dt)
    assert y < 1.0
    rates = [(y - 0.0) / dt]
    ys = [0.0, y]
    prev = y
    for _ in range(19):
        y = jl.step(1.0, dt)
        rates.append((y - prev) / dt)
        ys.append(y)
        prev = y
    # ahora puede llegar a 1.0 eventualmente
    assert y <= 1.0
    # La tasa está acotada por max_rate_per_s
    assert all(abs(r) <= 1.0 + 1e-6 for r in rates)
    # La variación de tasa está acotada por max_jerk_per_s2
    dr = [rates[i] - rates[i - 1] for i in range(1, len(rates))]
    # ignorar variaciones cuando la salida está saturada a 1.0 (clamp)
    filtered = [dr[i - 1] for i in range(1, len(ys)) if ys[i] < 0.999 and ys[i - 1] < 0.999]
    assert all(abs(x) <= 2.0 * dt + 1e-6 for x in filtered)
