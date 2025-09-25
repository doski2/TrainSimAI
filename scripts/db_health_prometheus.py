from __future__ import annotations

import argparse
import json
import os
import socket
import time
from pathlib import Path

from storage import db_check


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
        # For DB-level metrics include only the `db` label so tests and tooling
        # that expect a simple label can match. Instance/mode are included in
        # control metrics below.
        f.write(f'trainsim_db_connect_ok{{db="{db_path}"}} {conn_ok}\n')
        f.write("# HELP trainsim_db_can_write DB accepts a write (1=ok,0=fail)\n")
        f.write("# TYPE trainsim_db_can_write gauge\n")
        can_write_line = f'trainsim_db_can_write{{db="{db_path}"}} {write_ok}\n'
        f.write(can_write_line)
        # export DB retry counter if available (fallback to 0)
        retries = 0
        try:
            retries = int(res.get("retries", {}).get("count", 0))
        except Exception:
            retries = 0
        f.write("# HELP trainsim_db_retry_count_total Number of DB retry attempts seen during checks\n")
        f.write("# TYPE trainsim_db_retry_count_total counter\n")
        f.write(f'trainsim_db_retry_count_total{{db="{db_path}"}} {retries}\n')
        # Export control status metrics if available
        cs = _read_control_status(Path("data/control_status.json"))
        if cs:
            # last command timestamp
            lct = cs.get("last_command_time")
            lat = cs.get("last_ack_time")
            lcv = cs.get("last_command_value")
            stale = cs.get("stale")
            emergency = cs.get("emergency")
            # telemetry age: prefer cs['last_telemetry_time'] if present
            last_telemetry = cs.get("last_telemetry_time") or cs.get("last_telemetry")
            now = time.time()
            telem_age = None
            try:
                if last_telemetry is not None:
                    telem_age = now - float(last_telemetry)
            except Exception:
                telem_age = None
            f.write("# HELP trainsim_control_last_command_timestamp last command epoch timestamp (s)\n")
            f.write("# TYPE trainsim_control_last_command_timestamp gauge\n")
            try:
                if lct is not None:
                    f.write(
                        f'trainsim_control_last_command_timestamp{{instance="{instance}",mode="{mode}"}} {float(lct)}\n'
                    )
            except Exception:
                pass
            f.write("# HELP trainsim_control_last_ack_timestamp last ack epoch timestamp (s)\n")
            f.write("# TYPE trainsim_control_last_ack_timestamp gauge\n")
            try:
                if lat is not None:
                    ack_line = (
                        f'trainsim_control_last_ack_timestamp{{instance="{instance}",mode="{mode}"}} ' f"{float(lat)}\n"
                    )
                    f.write(ack_line)
            except Exception:
                pass
            # command latency (time since last command)
            f.write("# HELP trainsim_control_command_latency_seconds Time since last command was issued (s)\n")
            f.write("# TYPE trainsim_control_command_latency_seconds gauge\n")
            try:
                if lct is not None:
                    latency_val = now - float(lct)
                    latency_line = (
                        f'trainsim_control_command_latency_seconds{{instance="{instance}",mode="{mode}"}} '
                        f"{latency_val}\n"
                    )
                    f.write(latency_line)
            except Exception:
                pass
            # telemetry age
            f.write("# HELP trainsim_control_telemetry_age_seconds Age of last telemetry sample (s)\n")
            f.write("# TYPE trainsim_control_telemetry_age_seconds gauge\n")
            try:
                if telem_age is not None:
                    telem_line = (
                        f'trainsim_control_telemetry_age_seconds{{instance="{instance}",mode="{mode}"}} '
                        f"{float(telem_age)}\n"
                    )
                    f.write(telem_line)
            except Exception:
                pass
            f.write("# HELP trainsim_control_last_command_value last command value (0..1)\n")
            f.write("# TYPE trainsim_control_last_command_value gauge\n")
            try:
                if lcv is not None:
                    lcv_line = (
                        f'trainsim_control_last_command_value{{instance="{instance}",mode="{mode}"}} ' f"{float(lcv)}\n"
                    )
                    f.write(lcv_line)
            except Exception:
                pass
            # control status: 0=ok,1=stale,2=emergency
            f.write("# HELP trainsim_control_status 0=ok,1=stale,2=emergency\n")
            f.write("# TYPE trainsim_control_status gauge\n")
            try:
                status_val = 0
                if emergency:
                    status_val = 2
                elif stale:
                    status_val = 1
                status_line = f'trainsim_control_status{{instance="{instance}",mode="{mode}"}} ' f"{int(status_val)}\n"
                f.write(status_line)
            except Exception:
                pass


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="db_health_prometheus")
    p.add_argument("db", nargs="?", default="data/run.db", help="SQLite DB path")
    p.add_argument(
        "--out",
        default="/var/lib/node_exporter/textfile_collector/trainsim_db.prom",
        help="Output file for Prometheus textfile collector",
    )
    args = p.parse_args(argv)
    render_prom_file(args.db, args.out)
    # exit code 0 always (metrics file reflects state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
