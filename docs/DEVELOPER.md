## Developer guide - TrainSimAI

This file documents how developers should set up their environment, run linters and tests, and normalize EOL on Windows.

Prerequisites
- Windows x64, Python 3.11 recommended
- Create a virtualenv: `python -m venv .venv` and activate it

Install dependencies
```powershell
pip install -r requirements.txt
python -m pip install --user pre-commit black isort ruff
```

Pre-commit (recommended)
- Install hooks once per clone:
```powershell
pre-commit install
```
- To check all files locally (before pushing):
```powershell
pre-commit run --all-files --show-diff-on-failure
```

EOL handling on Windows
- Ensure the repository uses LF for python files. Recommended:
```powershell
git config core.autocrlf false
git add --renormalize .
git commit -m "chore: renormalize EOL to LF"
```
The repository contains a `.gitattributes` file which enforces `*.py text eol=lf`.

Formatting and linting
```powershell
python -m black .
python -m isort .
python -m ruff check . --select F,E,W
```

Run tests
```powershell
# run not-real (safe) tests
python -m pytest -q -m "not real"
```

If you need to run real-hardware tests use a self-hosted runner labelled `real-hw` and follow `docs/REAL-RUNNER.md`.

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
