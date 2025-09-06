from __future__ import annotations

import os
import shutil
from pathlib import Path
from datetime import datetime
import sys


def rotate_run(csv_path: Path) -> Path | None:
    if not csv_path.exists():
        print(f"[rotate] No existe: {csv_path}")
        return None
    try:
        size = csv_path.stat().st_size
    except OSError:
        size = 0
    if size <= 0:
        print(f"[rotate] Archivo vacío, no se rota: {csv_path}")
        return None

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = csv_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"run_{ts}.csv"

    # Evitar colisión si ya existe (raro)
    n = 1
    while dst.exists():
        dst = out_dir / f"run_{ts}_{n}.csv"
        n += 1

    # Usar rename/replace atómico
    try:
        shutil.move(str(csv_path), str(dst))
    except Exception as e:
        print(f"[rotate] Error moviendo {csv_path} -> {dst}: {e}")
        return None

    print(f"[rotate] {csv_path} -> {dst}")
    return dst


def main() -> None:
    # Permite ruta personalizada por arg o env
    arg_path = sys.argv[1] if len(sys.argv) > 1 else None
    env_path = os.environ.get("RUN_CSV_PATH")
    repo = Path(__file__).resolve().parents[1]
    default_path = repo / "data" / "runs" / "run.csv"
    path = Path(arg_path or env_path or default_path)
    rotate_run(path)


if __name__ == "__main__":
    main()

