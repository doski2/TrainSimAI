import sys
from pathlib import Path

# Seguridad: bloquea tests 'real' si no está el entorno adecuado
import os
# pyright: reportMissingImports=false
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    import pytest
else:
    # Shim mínimo para que Pylance no marque errores en edición:
    class _PytestShim:
        def skip(self, *args, **kwargs): ...
        def __getattr__(self, name):
            # Devuelve un decorador no-op (para marks, etc.)
            def _decorator(*a, **k):
                def _wrap(f): return f
                return _wrap
            return _decorator
    pytest = _PytestShim()  # type: ignore

def pytest_runtest_setup(item):
    if 'real' in getattr(item, 'keywords', {}):
        if os.environ.get('RUN_RD_TESTS') != '1':
            pytest.skip("Test 'real' requiere RUN_RD_TESTS=1 (hardware activo)")


# Add repository root to sys.path so tests can import runtime/* modules
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

