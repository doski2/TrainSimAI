from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from storage import db_check

# typing imports not required


def run(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="db_health", description="DB health checks for TrainSimAI (SQLite)"
    )
    p.add_argument(
        "db", nargs="?", default="data/run.db", help="Path to sqlite DB file"
    )
    p.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    args = p.parse_args(argv)
    db_path = Path(args.db)
    res = db_check.run_all_checks(db_path)
    out = json.dumps(res, indent=2) if args.pretty else json.dumps(res)
    print(out)
    # exit codes: 0 = all good, 1 = warning (connect ok but can_write failed), 2 = error (connect failed)
    conn_ok = bool(res.get("connect", {}).get("ok"))
    write_ok = bool(res.get("can_write", {}).get("ok"))
    if not conn_ok:
        return 2
    if conn_ok and not write_ok:
        return 1
    return 0


if __name__ == "__main__":
    code = run()
    sys.exit(code)
