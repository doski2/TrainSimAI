from __future__ import annotations

from pathlib import Path
import argparse
from storage import db_check
import json
import os
import socket


def _read_control_status(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def render_prom_file(db_path: str | Path, out_path: str | Path) -> None:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    res = db_check.run_all_checks(db_path)
    conn_ok = 1 if bool(res.get("connect", {}).get("ok")) else 0
    write_ok = 1 if bool(res.get("can_write", {}).get("ok")) else 0
    # labels
    instance = os.environ.get("TSC_INSTANCE") or socket.gethostname()
    mode = os.environ.get("TSC_MODE") or "unknown"
    with out.open("w", encoding="utf-8") as f:
        f.write("# trainsimai DB health metrics\n")
        f.write("# HELP trainsim_db_connect_ok DB file can be opened (1=ok,0=fail)\n")
        f.write("# TYPE trainsim_db_connect_ok gauge\n")
        f.write(f'trainsim_db_connect_ok{{db="{db_path}",instance="{instance}",mode="{mode}"}} {conn_ok}\n')
        f.write("# HELP trainsim_db_can_write DB accepts a write (1=ok,0=fail)\n")
        f.write("# TYPE trainsim_db_can_write gauge\n")
        f.write(f'trainsim_db_can_write{{db="{db_path}",instance="{instance}",mode="{mode}"}} {write_ok}\n')
        # Export control status metrics if available
        cs = _read_control_status(Path("data/control_status.json"))
        if cs:
            # last command timestamp
            lct = cs.get("last_command_time")
            lat = cs.get("last_ack_time")
            lcv = cs.get("last_command_value")
            f.write("# HELP trainsim_control_last_command_timestamp last command epoch timestamp (s)\n")
            f.write("# TYPE trainsim_control_last_command_timestamp gauge\n")
            try:
                if lct is not None:
                    f.write(f"trainsim_control_last_command_timestamp{{instance=\"{instance}\",mode=\"{mode}\"}} {float(lct)}\n")
            except Exception:
                pass
            f.write("# HELP trainsim_control_last_ack_timestamp last ack epoch timestamp (s)\n")
            f.write("# TYPE trainsim_control_last_ack_timestamp gauge\n")
            try:
                if lat is not None:
                    f.write(f"trainsim_control_last_ack_timestamp{{instance=\"{instance}\",mode=\"{mode}\"}} {float(lat)}\n")
            except Exception:
                pass
            f.write("# HELP trainsim_control_last_command_value last command value (0..1)\n")
            f.write("# TYPE trainsim_control_last_command_value gauge\n")
            try:
                if lcv is not None:
                    f.write(f"trainsim_control_last_command_value{{instance=\"{instance}\",mode=\"{mode}\"}} {float(lcv)}\n")
            except Exception:
                pass


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="db_health_prometheus")
    p.add_argument("db", nargs="?", default="data/run.db", help="SQLite DB path")
    p.add_argument("--out", default="/var/lib/node_exporter/textfile_collector/trainsim_db.prom", help="Output file for Prometheus textfile collector")
    args = p.parse_args(argv)
    render_prom_file(args.db, args.out)
    # exit code 0 always (metrics file reflects state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
