from __future__ import annotations

import csv
import os
from typing import Any, Dict


class CsvLogger:
    def __init__(self, path: str, delimiter: str = ";") -> None:
        self.path = path
        self.delimiter = delimiter
        self.fieldnames = None
        dirpath = os.path.dirname(path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)

    def write_row(self, row: Dict[str, Any]) -> None:
        if self.fieldnames is None:
            self.fieldnames = sorted(row.keys())
            with open(self.path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=self.fieldnames, delimiter=self.delimiter)
                w.writeheader()
                w.writerow({k: row.get(k, "") for k in self.fieldnames})
        else:
            missing = [k for k in row.keys() if k not in self.fieldnames]
            if missing:
                # reescribir con cabecera extendida (simple y robusto para MVP)
                self.fieldnames.extend(sorted(missing))
                with open(self.path, "r", encoding="utf-8") as f:
                    lines = f.read().splitlines()
                with open(self.path, "w", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=self.fieldnames, delimiter=self.delimiter)
                    w.writeheader()
                    for line in lines[1:]:
                        f.write(line + "\n")
            with open(self.path, "a", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=self.fieldnames, delimiter=self.delimiter)
                w.writerow({k: row.get(k, "") for k in self.fieldnames})
