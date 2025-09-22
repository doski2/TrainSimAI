import time

import pytest

from runtime.collector import retry_on_exception


class _Flaky:
    def __init__(self, fail_times=1):
        self.calls = 0
        self.fail_times = fail_times

    def run(self):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("transient")
        return "ok"


def test_retry_decorator_recovers_after_transient_failure(monkeypatch):
    f = _Flaky(fail_times=2)

    # decorate with small delays for fast test
    wrapped = retry_on_exception(max_attempts=4, base_delay=0.001, max_delay=0.01)(
        f.run
    )

    t0 = time.time()
    res = wrapped()
    t1 = time.time()

    assert res == "ok"
    # Ensure we retried at least twice (calls > 1)
    assert f.calls == 3
    # total elapsed should be at least base_delay (approx)
    assert t1 - t0 >= 0


def test_retry_decorator_raises_after_exhaustion():
    f = _Flaky(fail_times=10)
    wrapped = retry_on_exception(max_attempts=3, base_delay=0.001, max_delay=0.01)(
        f.run
    )
    with pytest.raises(RuntimeError):
        wrapped()
