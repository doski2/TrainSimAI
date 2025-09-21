Add safety tests for RD ack watchdog and ControlLoop ACK behavior

- Adds two safety-marked tests that validate critical safety behavior:
  1. `tests/test_ack_watchdog_integration.py` — integration-style test verifying that `ControlLoop.monitor_ack_timeout()` triggers emergency when no ACK arrives and clears emergency when an ACK is written.
  2. `tests/test_ack_watchdog_requeue_escalation.py` — exercises `ingestion.RDClient`'s ack-watchdog background worker to ensure it requeues, records retries, and escalates to emergency when ACKs never arrive.

Why:
- These tests cover safety-critical flows: missing actuator acknowledgements and the background watchdog escalation path. They help catch regressions in retry/escalation logic and simplify on-call debugging.

How to test locally:
- Ensure virtualenv active and dev deps installed (mypy, pytest, etc).
- Run only safety tests:
  ```powershell
  python -m pytest -q -m safety
  ```
- Run a single test for quicker feedback:
  ```powershell
  python -m pytest -q tests/test_ack_watchdog_integration.py -k monitor_ack_timeout -m safety
  ```

Checklist for reviewers:
- [ ] CI runs the `safety` marker job and has adequate timeout/resources.
- [ ] Tests are deterministic enough on CI — if flaky, consider further timeouts or mocking.
- [ ] Confirm that new tests are acceptable to run in PR (they are fast with shortened timeouts).

Notes:
- The tests use `FakeRailDriver` and manipulate timestamps or short timeouts to avoid long sleeps; they run quickly locally and in CI.
- Optional: add verification of Prometheus metrics if `prometheus_client` is installed in CI.
