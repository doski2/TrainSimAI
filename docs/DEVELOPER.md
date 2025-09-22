# Developer instructions

Windows development quickstart

- Activate virtualenv:
  - PowerShell: `. .venv\Scripts\Activate.ps1`

- Ensure UTF-8 output in PowerShell (helps pre-commit hooks and CI logs):
  - `$env:PYTHONIOENCODING = 'utf-8'`

- Install development dependencies (if using `requirements-dev.txt`):
  - `python -m pip install -r requirements-dev.txt`

- Install and run pre-commit hooks locally:
  - `python -m pip install pre-commit`
  - `pre-commit install`
  - `python -m pre_commit run --all-files`

- Run linters and tests:
  - `python -m ruff check .`
  - `pytest -q`

CI notes

- The hosted CI runs the `not-real` workflow which executes `pre-commit` and `pytest` for non-hardware tests.
- Tests marked with `@pytest.mark.real` run only on self-hosted Windows runners and require manual validation via `scripts/validate_real_runner.ps1`.
