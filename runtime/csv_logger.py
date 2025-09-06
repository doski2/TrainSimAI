from __future__ import annotations

import csv
import os
from typing import Any, Dict, Iterable, List, TextIO
import time


class CsvLogger:
    def __init__(self, path: str, delimiter: str = ";") -> None:
        self.path = path
        self.delimiter = delimiter
        self.fieldnames: List[str] | None = None
        # Mantenemos un handle para reducir errores de sharing en Windows
        self._file: TextIO | None = None  # persistent handle to mitigate Windows share violations
        self._writer: csv.DictWriter[str] | None = None
        dirpath = os.path.dirname(path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)

    def init_with_fields(self, fields: Iterable[str]) -> None:
        """Fija la cabecera con un superset conocido antes de la primera fila."""
        # Normaliza, deduplica y ordena
        names = [str(x) for x in fields]
        self.fieldnames = sorted(list(dict.fromkeys(names)))
        # Abre nuevo archivo con cabecera fija
        self._open_new()
        assert self._writer is not None
        self._writer.writeheader()
        # Asegura que el encabezado quede en disco
        if self._file:
            self._file.flush()

    def write_row(self, row: Dict[str, Any]) -> None:
        if self.fieldnames is None:
            # Primera escritura: crear archivo y mantener handle abierto
            self.fieldnames = sorted(row.keys())
            self._open_new()
            assert self._writer is not None
            self._writer.writeheader()
            self._writer.writerow({k: row.get(k, "") for k in self.fieldnames})
            if self._file:
                self._file.flush()
            return

        # A partir de la segunda escritura
        missing = [k for k in row.keys() if k not in self.fieldnames]
        if missing:
            # Ampliar cabecera: reescribir archivo con nueva cabecera y remapear filas antiguas
            self.fieldnames.extend(sorted(missing))
            self._close()
            existing_rows = []
            if os.path.exists(self.path):
                try:
                    with open(self.path, newline="", encoding="utf-8", errors="ignore") as f_in:
                        r = csv.DictReader(f_in, delimiter=self.delimiter)
                        existing_rows = list(r)
                except Exception:
                    existing_rows = []
            with open(self.path, "w", newline="", encoding="utf-8") as f_out:
                w = csv.DictWriter(f_out, fieldnames=self.fieldnames, delimiter=self.delimiter)
                w.writeheader()
                for rr in existing_rows:
                    w.writerow({k: rr.get(k, "") for k in self.fieldnames})
            # Reabrir en modo append persistente
            self._open_append()

        if self._writer is None:
            self._open_append()
        assert self._writer is not None
        self._writer.writerow({k: row.get(k, "") for k in self.fieldnames})
        if self._file:
            self._file.flush()

    # --- Internals ---
    def _open_new(self) -> None:
        self._close()
        assert self.fieldnames is not None
        self._file = open(self.path, "w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, fieldnames=self.fieldnames, delimiter=self.delimiter)

    def _open_append(self, retries: int = 5, delay: float = 0.05) -> None:
        self._close()
        last_err = None
        for _ in range(max(1, retries)):
            try:
                assert self.fieldnames is not None
                self._file = open(self.path, "a", newline="", encoding="utf-8")
                self._writer = csv.DictWriter(self._file, fieldnames=self.fieldnames, delimiter=self.delimiter)
                return
            except PermissionError as e:
                last_err = e
                time.sleep(delay)
        if last_err:
            raise last_err

    def _close(self) -> None:
        try:
            if self._file:
                self._file.close()
        finally:
            self._file = None
            self._writer = None
