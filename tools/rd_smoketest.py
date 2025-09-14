import time, argparse, os
from runtime.actuators import load_rd_from_spec, send_to_rd, debug_trace


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rd", default=os.getenv("TSC_RD", ""), help="modulo:atributo (objeto o factory)")
    ap.add_argument("--pattern", default="0,0.5,1,0.5,0", help="valores de freno [0..1] separados por comas")
    ap.add_argument("--step-ms", type=int, default=800)
    args = ap.parse_args()

    debug_on = True
    os.makedirs("data", exist_ok=True)
    open("data\\rd_send.log", "w").close()

    rd, where = load_rd_from_spec(args.rd)
    if not rd:
        print("[rd_smoketest] NO-RD. Revisa --rd o TSC_RD")
        return 2
    print(f"[rd_smoketest] RD={where}")
    vals = [float(x) for x in args.pattern.split(",")]
    for v in vals:
        thr_ok, brk_ok, thr_m, brk_m = send_to_rd(rd, None, v)
        debug_trace(debug_on, f"smoke send(b={v}) applied(brk={brk_ok}:{brk_m})")
        time.sleep(args.step_ms / 1000.0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
