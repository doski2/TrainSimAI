from __future__ import annotations

import csv
import os
from typing import Any, Dict
import time


class CsvLogger:
    def __init__(self, path: str, delimiter: str = ";") -> None:
        self.path = path
        self.delimiter = delimiter
        self.fieldnames = None
        # Mantenemos un handle para reducir errores de sharing en Windows
        self._file = None  # persistent handle to mitigate Windows share violations
        self._writer = None
        dirpath = os.path.dirname(path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)

    def init_with_fields(self, fields):
        """Fija la cabecera con un superset conocido antes de la primera fila."""
        # Normaliza, deduplica y ordena
        fields = sorted(list(dict.fromkeys(fields)))
        self.fieldnames = fields
        # Abre nuevo archivo con cabecera fija
        self._open_new()
        self._writer.writeheader()

    def write_row(self, row: Dict[str, Any]) -> None:
        if self.fieldnames is None:
            # Primera escritura: crear archivo y mantener handle abierto
            self.fieldnames = sorted(row.keys())
            self._open_new()
            self._writer.writeheader()
            self._writer.writerow({k: row.get(k, "") for k in self.fieldnames})
            return

        # A partir de la segunda escritura
        missing = [k for k in row.keys() if k not in self.fieldnames]
        if missing:
            # Ampliar cabecera: reescribir archivo con nueva cabecera
            self.fieldnames.extend(sorted(missing))
            self._close()
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    lines = f.read().splitlines()
            except FileNotFoundError:
                lines = []
            with open(self.path, "w", newline="", encoding="utf-8") as f:
                # Escribimos solo la nueva cabecera, luego copiamos las filas antiguas tal cual
                w = csv.DictWriter(f, fieldnames=self.fieldnames, delimiter=self.delimiter)
                w.writeheader()
                for line in lines[1:]:
                    f.write(line + "\n")
            # Reabrir en modo append persistente
            self._open_append()

        if self._writer is None:
            self._open_append()
        self._writer.writerow({k: row.get(k, "") for k in self.fieldnames})

    # --- Internals ---
    def _open_new(self) -> None:
        self._close()
        self._file = open(self.path, "w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, fieldnames=self.fieldnames, delimiter=self.delimiter)

    def _open_append(self, retries: int = 5, delay: float = 0.05) -> None:
        self._close()
        last_err = None
        for _ in range(max(1, retries)):
            try:
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
