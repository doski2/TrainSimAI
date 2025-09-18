import sys
from pathlib import Path

# Seguridad: bloquea tests 'real' si no está el entorno adecuado
import os
# pyright: reportMissingImports=false
import pytest

def pytest_runtest_setup(item):
    if 'real' in getattr(item, 'keywords', {}):
        if os.environ.get('RUN_RD_TESTS') != '1':
            pytest.skip("Test 'real' requiere RUN_RD_TESTS=1 (hardware activo)")


# Add repository root to sys.path so tests can import runtime/* modules
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

