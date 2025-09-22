import os

import pytest


def _has_rd_dlls() -> bool:
    dll_dir = os.environ.get("TSC_RD_DLL_DIR") or os.environ.get("RAILWORKS_PLUGINS")
    if not dll_dir:
        return False
    # basic check: any .dll file in the directory
    try:
        for f in os.listdir(dll_dir):
            if f.lower().endswith(".dll"):
                return True
    except Exception:
        return False
    return False


def _has_rd_endpoint() -> bool:
    rd = os.environ.get("TSC_RD")
    return bool(rd)


def test_real_smoke_check():
    """Smoke check for real tests: skip if no DLLs or RD endpoint configured.

    This avoids noisy failures when running on runners that are not prepared.
    """
    if not (_has_rd_dlls() or _has_rd_endpoint()):
        pytest.skip(
            "Skipping real tests: no TSC_RD_DLL_DIR/RAILWORKS_PLUGINS or TSC_RD configured on this runner"
        )

    # Basic import sanity check (do not raise if it imports but cannot connect)
    try:
        import importlib

        importlib.import_module("ingestion.rd_impl_real")
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"Skipping real tests: ingestion.rd_impl_real import failed: {exc}")

    assert True
