from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


class CSVLogger:
    """Logger CSV simple y seguro para Windows.

    Compatibilidad con la API previa usada por `runtime.collector`:
      CsvLogger(path, delimiter=';', base_order=[...])
      csvlog.init_with_fields(fields)
      csvlog.write_row(row)

    Esta implementación escribe siempre en modo append y no reescribe el
    fichero entero cuando aparecen columnas nuevas (para evitar errores
    de bloqueo en Windows). Si aparece una fila con columnas no listadas
    en la cabecera, las columnas extra se ignoran al escribir.
    """

    def __init__(
        self,
        path: str | os.PathLike,
        delimiter: str = ";",
        base_order: Optional[Iterable[str]] = None,
    ) -> None:
        self.path = Path(path).resolve()
        self.delimiter = delimiter
        self.fieldnames: List[str] | None = None
        self._base_order: List[str] = list(dict.fromkeys([str(x) for x in (base_order or [])]))
        # prepare dir
        if self.path.parent:
            os.makedirs(self.path.parent, exist_ok=True)

    def init_with_fields(self, fields: Iterable[str]) -> None:
        """Establece la cabecera (superset conocido) y crea/abre el archivo en modo append."""
        names = [str(x) for x in fields]
        uniq = list(dict.fromkeys(names))
        prefix = [c for c in self._base_order if c in uniq]
        rest = [c for c in uniq if c not in self._base_order]
        self.fieldnames = prefix + rest
        # if file does not exist or empty, write header
        if not self.path.exists() or self.path.stat().st_size == 0:
            # mypy/ruff: asegurar que fieldnames no es None
            fieldnames = self.fieldnames
            assert fieldnames is not None
            with self.path.open("a", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(
                    f,
                    fieldnames=fieldnames,
                    delimiter=self.delimiter,
                    extrasaction="ignore",
                )
                w.writeheader()

    def write_row(self, row: Dict[str, Any]) -> None:
        """Escribe una fila usando solo las columnas conocidas (si faltan, se ignoran)."""
        if self.fieldnames is None:
            # Derivar cabecera mínima de la fila respetando base_order
            keys_in = list(dict.fromkeys(list(row.keys())))
            prefix = [c for c in self._base_order if c in keys_in]
            rest = [c for c in keys_in if c not in self._base_order]
            self.fieldnames = prefix + rest
            # escribir header si archivo vacío
            if not self.path.exists() or self.path.stat().st_size == 0:
                fieldnames = self.fieldnames
                assert fieldnames is not None
                with self.path.open("a", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(
                        f,
                        fieldnames=fieldnames,
                        delimiter=self.delimiter,
                        extrasaction="ignore",
                    )
                    w.writeheader()

        # Open in append mode and write row mapping only known fields
        assert self.fieldnames is not None
        fieldnames = self.fieldnames
        with self.path.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(
                f,
                fieldnames=fieldnames,
                delimiter=self.delimiter,
                extrasaction="ignore",
            )
            out = {k: row.get(k, "") for k in self.fieldnames}
            w.writerow(out)

    def close(self) -> None:
        # No persistent handle to cerrar; placeholder para compatibilidad
        return


# Compatibilidad hacia atrás: algunos módulos importan `CsvLogger`
CsvLogger = CSVLogger
