"""Ejecuta un sweep de parámetros para `runtime.control_loop` y genera un CSV resumen.

Resumen por ejecución:
- rise_per_s, startup_gate_s, hold_s, fall_per_s, hz, duration, run_file,
  rd_zero_count, rd_intermediate_count, rd_full_count, rd_total

Notas:
- El script invoca `python -u -m runtime.control_loop --source csv --run <run>` con `TSC_RD_DEBUG=1`.
- Antes de cada ejecución, restablece `data/rd_send.log` para capturar solo los envíos de la ejecución.
- Analiza `data/rd_send.log` tras la ejecución y cuenta valores 0.0, 1.0 y 0<x<1.

Uso:
  python scripts/sweep_brake_params.py

"""

import csv
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT.joinpath("data")
RD_LOG = DATA.joinpath("rd_send.log")
SUMMARY_DIR = DATA.joinpath("sweep")
SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
SUMMARY_CSV = SUMMARY_DIR.joinpath("summary.csv")

# Run file por defecto (asegúrate de revisarlo antes de ejecutar)
RUN_FILE = Path(os.environ.get("SWEEP_RUN_FILE", "data/runs/test_brake.csv"))

# Parámetros a barrer (valores razonables para empezar)
rise_vals = [0.05, 0.1, 0.2]
startup_vals = [0.5, 1.0, 2.0]
hold_vals = [0.1, 0.2]
fall_vals = [1.0]
hz = 5
duration = 12  # segundos por ejecución

# Encabezados del CSV resumen
with SUMMARY_CSV.open("w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(
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
        ]
    )


# Función para resetear log
def reset_rd_log():
    DATA.mkdir(parents=True, exist_ok=True)
    RD_LOG.write_text("")


# Función para analizar el log
def analyze_rd_log():
    if not RD_LOG.exists():
        return 0, 0, 0
    z = i = m = 0
    for ln in RD_LOG.read_text(encoding="utf-8", errors="ignore").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            # JSONL simple: buscar '"value":' y parsear
            if '"value"' in ln:
                # extraer número simple
                idx = ln.index('"value"')
                sub = ln[idx:]
                # buscar ':' y luego , or }
                colon = sub.index(":")
                rest = sub[colon + 1 :]
                # limpiar
                sval = rest.split(",")[0].split("}")[0].strip()
                v = float(sval)
            else:
                # línea humana 'set_brake(0.0)'
                if "set_brake" in ln:
                    s = ln[ln.index("set_brake") :]
                    v = float(s[s.index("(") + 1 : s.index(")")])
                else:
                    continue
        except Exception:
            continue
        if v == 0.0:
            z += 1
        elif v == 1.0:
            m += 1
        else:
            i += 1
    return z, i, m


# Ejecutar sweep
for r in rise_vals:
    for s in startup_vals:
        for h in hold_vals:
            for fall in fall_vals:
                print(f"[sweep] running r={r} s={s} h={h} fall={fall}")
                reset_rd_log()
                env = os.environ.copy()
                env["TSC_RD_DEBUG"] = "1"
                # no append, reset already done
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
                    str(hz),
                    "--duration",
                    str(duration),
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
                # esperar a que termine
                p.wait(timeout=duration + 10)
                time.sleep(0.2)
                z, i_count, m_count = analyze_rd_log()
                total = z + i_count + m_count
                # append al CSV resumen
                with SUMMARY_CSV.open("a", newline="", encoding="utf-8") as fh:
                    w = csv.writer(fh)
                    w.writerow(
                        [
                            r,
                            s,
                            h,
                            fall,
                            hz,
                            duration,
                            str(RUN_FILE),
                            z,
                            i_count,
                            m_count,
                            total,
                        ]
                    )

print(f"Sweep finished. Summary: {SUMMARY_CSV}")
