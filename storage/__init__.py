"""Storage package for TrainSimAI.

Exports a RunStore implementation backed by SQLite (WAL) so callers can
do: ``from storage import RunStore``.

This file is intentionally small — concrete implementations live in
``storage/run_store_sqlite.py``.
"""

from .run_store_sqlite import RunStore

__all__ = ["RunStore"]
# Storage package for TrainSimAI (SQLite/WAL)
# Storage package for TrainSimAI
