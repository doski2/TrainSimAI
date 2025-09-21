### What this PR does
- Adds two safety tests for RD ACK/watchdog behavior:
  - `tests/test_ack_watchdog_ack_success.py`
  - `tests/test_ack_watchdog_delayed_ack.py`
- Adds a small fix in `ingestion/rd_client.py`: `_clear_retries(name)` is called when an ACK is confirmed to reset retry counters (best-effort).
- Updates docs: `CONTRIBUTING.md` (commands for ruff/mypy/pytest) and `README.md` (Operación section).

### Files changed
- `tests/test_ack_watchdog_ack_success.py`
- `tests/test_ack_watchdog_delayed_ack.py`
- `ingestion/rd_client.py` (retry-counter clear)
- `CONTRIBUTING.md`
- `README.md`

### How to verify locally
```powershell
& ./.venv/Scripts/Activate.ps1
python -m pytest -q -m safety -o addopts=
python -m ruff check . --select F,E,W
python -m mypy --ignore-missing-imports --follow-imports=silent ingestion runtime
```

### Checklist for reviewers
- [ ] Verify safety tests pass in CI (`pytest -m safety`)
- [ ] Confirm `rd_client` change does not introduce regressions (review logs/metrics)
- [ ] Confirm docs are accurate and commands run on Windows PowerShell

### Notes
- The `_clear_retries` change is best-effort to avoid leaving stale retry counters after ACKs; metrics may still show historical counts.
- If you prefer a different approach (e.g., deleting keys instead of setting to 0), tell me and I can adjust the patch.
