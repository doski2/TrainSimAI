from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Iterable, Optional


class LuaEventBus:
    def __init__(
        self, path: str, from_end: bool = True, create_if_missing: bool = True
    ) -> None:
        self.path = path
        self.pos = 0
        # Crea el fichero y carpeta si no existen (evita fallos y bloqueos)
        if create_if_missing:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            try:
                open(self.path, "a", encoding="utf-8").close()
            except Exception:
                pass
        if from_end and os.path.exists(self.path):
            self.pos = os.path.getsize(self.path)

    def poll(self) -> Optional[Dict[str, Any]]:
        # Si no existe, devuelve None sin dormir (no frenes el muestreo)
        if not os.path.exists(self.path):
            return None
        with open(self.path, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(self.pos)
            line = f.readline()
            if not line:
                return None
            self.pos = f.tell()
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                return None

    def stream(self) -> Iterable[Dict[str, Any]]:
        while True:
            evt = self.poll()
            if evt:
                yield evt
            else:
                time.sleep(0.05)
