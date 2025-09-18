from __future__ import annotations
import argparse
import json
import os
import re
import shutil
from datetime import datetime

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def parse_kpi(path: str):
    """
    Busca una línea tipo:
    [KPI] arrivals=7  arrivals_ok=0.571  mean_margin_last50_kph=7.434  monotonicity_bumps=1
    """
    txt = open(path, "r", encoding="utf-8", errors="ignore").read()
    m = re.search(
        r"\[KPI\]\s*arrivals=(\d+)\s+arrivals_ok=([0-9.]+)\s+mean_margin_last50_kph=([\-0-9.]+)\s+monotonicity_bumps=(\d+)",
        txt
    )
    if not m:
        raise SystemExit("[autotune] No pude leer KPI de kpi_latest.txt")
    arrivals = int(m.group(1))
    ok_rate = float(m.group(2))
    mean_margin = float(m.group(3))
    bumps = int(m.group(4))
    return arrivals, ok_rate, mean_margin, bumps

def load_profile(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_profile(path: str, data: dict):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = f"{path}.{ts}.bak"
    shutil.copyfile(path, bak)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return bak

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default=os.getenv("TSC_PROFILE", "profiles/BR146.json"))
    ap.add_argument("--kpi-file", default="data/runs/kpi_latest.txt")
    ap.add_argument("--target", type=float, default=0.8)
    ap.add_argument("--step", type=float, default=0.5)
    ap.add_argument("--min", dest="vmin", type=float, default=2.0)
    ap.add_argument("--max", dest="vmax", type=float, default=6.0)
    args = ap.parse_args()

    arrivals, ok_rate, mean_margin, bumps = parse_kpi(args.kpi_file)
    print(f"[autotune] KPI arrivals={arrivals} ok={ok_rate:.3f} mean_margin={mean_margin:.3f} bumps={bumps}")

    # Solo ajustamos con KPI verde para no aprender “ruido”
    if ok_rate < 0.90 or bumps > 0:
        print("[autotune] KPI NO VERDE (ok<0.90 o bumps>0) -> no ajusto perfil.")
        return 0

    prof = load_profile(args.profile)
    v = float(prof.get("v_margin_kph", 3.5))
    err = mean_margin - args.target
    if abs(err) < 0.3:
        print(f"[autotune] mean_margin ya cerca del objetivo ({args.target:.1f}). v_margin_kph se queda en {v:.2f}")
        return 0

    # Si el margen medio está alto, subimos v_margin_kph; si está bajo, lo bajamos.
    # (Regla empírica, paso fijo ±0.5)
    dv = args.step if err > 0 else -args.step
    new_v = clamp(v + dv, args.vmin, args.vmax)
    if abs(new_v - v) < 1e-9:
        print(f"[autotune] En límites [{args.vmin},{args.vmax}] -> no ajusto.")
        return 0

    prof["v_margin_kph"] = new_v
    bak = save_profile(args.profile, prof)

    os.makedirs("data", exist_ok=True)
    with open("data/autotune.log", "a", encoding="utf-8") as log:
        log.write(f"{datetime.now().isoformat(timespec='seconds')} profile={args.profile} v_margin_kph {v:.2f} -> {new_v:.2f} (err={err:.2f}) bak={bak}\n")
    print(f"[autotune] v_margin_kph: {v:.2f} -> {new_v:.2f} (err={err:.2f}). Backup: {bak}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
