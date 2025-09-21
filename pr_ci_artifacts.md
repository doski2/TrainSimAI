This PR adds artifact collection and upload for the `safety-tests` job in `ci-mypy-safety.yml`.

Why: when safety tests fail we need diagnostic artifacts (e.g. `data/control_status.json`, `data/rd_ack.json`, `data/rd_send.log`) to debug failures in CI.

Files changed:
- `.github/workflows/ci-mypy-safety.yml` (add collection + upload-artifact steps)

How to test:
- Run the `safety-tests` job in GitHub Actions and confirm that when a safety test fails the `safety-diagnostics` artifact appears in the run's Artifacts section.
