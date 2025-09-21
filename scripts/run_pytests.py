#!/usr/bin/env python3
"""Run pytest programmatically after preparing test prerequisites.

This ensures the helper that creates `data/run.db` runs in the same process
and working directory as pytest, avoiding path/cwd races when invoked from
PowerShell wrappers.
"""
from __future__ import annotations

import argparse
# minimal runner: keep imports local to avoid unused-import warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run pytest with helpers")
    parser.add_argument("--mode", choices=("all", "not-real", "real"), default="not-real")
    parser.add_argument("--pytest-args", nargs="*", help="Additional args passed to pytest")
    args = parser.parse_args(argv)

    # Ensure minimal DB for tests that expect it when running not-real
    if args.mode == "not-real":
        try:
            from scripts._ensure_test_db import ensure_db

            ensure_db()
        except Exception:
            # best-effort; continue to pytest which may skip or fail
            pass

    # Build pytest args
    py_args = []
    if args.mode == "not-real":
        py_args += ["-m", "not real"]
    elif args.mode == "real":
        py_args += ["-m", "real"]
    # include user-supplied args
    if args.pytest_args:
        py_args += args.pytest_args

    # Run pytest programmatically
    import pytest

    return pytest.main(py_args)


if __name__ == "__main__":
    raise SystemExit(main())
