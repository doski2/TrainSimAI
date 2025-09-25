"""Sweep brake parameter sweep and write a CSV summary.

Small, self-contained implementation safe for CI. Uses the raildriver stub to
avoid loading native DLLs on hosted runners.
"""

import csv
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DATA.mkdir(parents=True, exist_ok=True)
RD_LOG = DATA / "rd_send.log"
SUMMARY_DIR = DATA / "sweep"
SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
SUMMARY_CSV = SUMMARY_DIR / "summary.csv"

# Defaults
RUN_FILE = Path(os.environ.get("SWEEP_RUN_FILE", "data/runs/test_brake.csv"))
RISE_VALS = [0.05, 0.1, 0.2]
STARTUP_VALS = [0.5, 1.0, 2.0]
HOLD_VALS = [0.1, 0.2]
FALL_VALS = [1.0]
HZ = 5
DURATION = 12


def write_header():
    with SUMMARY_CSV.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerow(
            [
                "rise_per_s",
                "startup_gate_s",
                "hold_s",
                "fall_per_s",
                "hz",
                "duration",
                "run_file",
                "rd_zero_count",
                "rd_intermediate_count",
                "rd_full_count",
                "rd_total",
                # Game metrics
                "score",
                "smoothness",
                "penalties",
            ]
        )


def reset_rd_log():
    RD_LOG.write_text("")


def analyze_rd_log():
    """Parse `rd_send.log` and return counts + numeric values list.

    Returns: (zeros, intermediate, full, values_list)
    """
    if not RD_LOG.exists():
        return 0, 0, 0, []
    zeros = inter = full = 0
    values = []
    text = RD_LOG.read_text(encoding="utf-8", errors="ignore")
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            if '"value"' in ln:
                idx = ln.index('"value"')
                sub = ln[idx:]
                colon = sub.index(":")
                rest = sub[colon + 1 :]
                sval = rest.split(",")[0].split("}")[0].strip()
                v = float(sval)
            elif "set_brake" in ln:
                s = ln[ln.index("set_brake") :]
                v = float(s[s.index("(") + 1 : s.index(")")])
            else:
                continue
        except Exception:
            continue
        values.append(v)
        if v == 0.0:
            zeros += 1
        elif v == 1.0:
            full += 1
        else:
            inter += 1
    return zeros, inter, full, values


def compute_game_metrics(values, hz=HZ):
    """Compute simple game metrics from a list of brake values.

    - smoothness: 0..100 (higher is smoother). Computed from RMS of first
      derivative (delta per sample). Lower derivative => higher smoothness.
    - penalties: count of abrupt changes (abs(delta) > 0.5).
    - score: base on smoothness minus penalty cost.

    These are intentionally simple heuristics for gameplay and reproducibility.
    """
    if not values:
        return 0.0, 0.0, 0
    # compute deltas between consecutive samples
    deltas = [values[i] - values[i - 1] for i in range(1, len(values))]
    # rms of derivative
    import math

    rms = math.sqrt(sum(d * d for d in deltas) / len(deltas)) if deltas else 0.0
    # normalize rms to a 0..100 smoothness score (heuristic)
    smoothness = max(0.0, 100.0 - (rms * 100.0))
    # count penalties (abrupt changes)
    penalties = sum(1 for d in deltas if abs(d) > 0.5)
    # score: smoothness reduced by penalty cost
    score = max(0.0, smoothness - penalties * 10.0)
    # round for CSV friendliness
    return round(score, 2), round(smoothness, 2), int(penalties)


def run_sweep():
    write_header()
    for r in RISE_VALS:
        for s in STARTUP_VALS:
            for h in HOLD_VALS:
                for fall in FALL_VALS:
                    print(f"[sweep] running r={r} s={s} h={h} fall={fall}")
                    reset_rd_log()
                    env = os.environ.copy()
                    env["TSC_RD_DEBUG"] = "1"
                    cmd = [
                        "python",
                        "-u",
                        "-m",
                        "runtime.control_loop",
                        "--source",
                        "csv",
                        "--run",
                        str(RUN_FILE),
                        "--mode",
                        "brake",
                        "--rd",
                        "runtime.raildriver_stub:rd",
                        "--hz",
                        str(HZ),
                        "--duration",
                        str(DURATION),
                        "--out",
                        str(DATA.joinpath(f"run.ctrl_r{r}_s{s}_h{h}_f{fall}.csv")),
                        "--rise-per-s",
                        str(r),
                        "--fall-per-s",
                        str(fall),
                        "--startup-gate-s",
                        str(s),
                        "--hold-s",
                        str(h),
                    ]
                    p = subprocess.Popen(cmd, env=env, cwd=str(ROOT))
                    try:
                        p.wait(timeout=DURATION + 10)
                    except subprocess.TimeoutExpired:
                        p.kill()
                        print("Process timeout, killed")
                    time.sleep(0.2)
                    zeros, inter, full, values = analyze_rd_log()
                    total = zeros + inter + full
                    score, smoothness, penalties = compute_game_metrics(values, hz=HZ)
                    with SUMMARY_CSV.open("a", newline="", encoding="utf-8") as fh:
                        csv.writer(fh).writerow(
                            [
                                r,
                                s,
                                h,
                                fall,
                                HZ,
                                DURATION,
                                str(RUN_FILE),
                                zeros,
                                inter,
                                full,
                                total,
                                score,
                                smoothness,
                                penalties,
                            ]
                        )
    print(f"Sweep finished. Summary: {SUMMARY_CSV}")


if __name__ == "__main__":
    run_sweep()
