# Contributing to TrainSimAI

This project uses Python 3.11 (virtualenv recommended). This file documents how to run tests and linters locally and how to contribute small fixes.

## Setup

Create and activate a virtual environment (PowerShell):

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

## Running tests

The test suite uses `pytest`. The repository's `pytest.ini` runs only tests marked `real` by default; to run the full suite use:

```powershell
python -m pytest -q -o addopts=
```

To run a single test file:

```powershell
python -m pytest tests/test_controls.py -q
```

## Linters

This repository uses `ruff` and `flake8`.

Run ruff and auto-fix:

```powershell
ruff check . --fix
```

Then run flake8 to catch any remaining style issues:

```powershell
flake8 .
```

## Control aliases (testing)

A canonical controls mapping is provided in `profiles/controls.py`. Tests and `ingestion/rd_client.py` can accept an injected mapping for determinism during tests. To run code with a custom mapping, set the environment variable `TSC_CONTROL_ALIASES_FILE` to a JSON file with the mapping, or modify test fixtures to pass a mapping into `RDClient` during construction.

## CI suggestions

- Add a GitHub Actions workflow to run `ruff check . --fix` (or `ruff check .`), `flake8 .`, and `pytest -q -o addopts=` on push and pull requests.

## Style and tests

- Prefer using `assert` in tests rather than returning boolean values. The repository uses `pytest`.
- Keep lines <= 120 characters to satisfy flake8 limits.

If you want, I can add a minimal GitHub Actions workflow and adjust the `README.md` to reference these instructions.
