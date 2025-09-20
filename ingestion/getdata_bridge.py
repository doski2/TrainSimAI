from __future__ import annotations
import os
import time
import json
import sys
import argparse
from pathlib import Path

GETDATA = Path(
    os.getenv(
        "TSC_GETDATA_FILE",
        r"C:\\Program Files (x86)\\Steam\\steamapps\\common\\RailWorks\\plugins\\GetData.txt",
    )
)
BUS = Path("data/lua_eventbus.jsonl")
BUS.parent.mkdir(parents=True, exist_ok=True)


def emit(d: dict) -> None:
    with BUS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")


def read_pairs(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    last = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("ControlName:"):
            last = line[12:].strip()
        elif line.startswith("ControlValue:") and last:
            out[last] = line[13:].strip()
            last = None
    return out


def fnum(s: str | None) -> float | None:
    if s is None:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def run(
    duration: float = 0.0,
    interval: float = 0.25,
    verbose: bool = True,
) -> None:
    last_current_kph: float | None = None
    last_next_kph: float | None = None
    last_next_dist: float | None = None
    last_probe_ts = 0.0

    if verbose:
        print(f"[bridge] tail → {GETDATA}")
    # Señal de vida
    emit({"type": "getdata_hello", "path": str(GETDATA)})
    last_sig = (0, 0)
    t0 = time.time()
    while True:
        if duration > 0 and (time.time() - t0) >= duration:
            if verbose:
                print("[bridge] done (duration reached)")
            return
        if not GETDATA.exists():
            time.sleep(interval)
            continue

        txt = GETDATA.read_text(encoding="utf-8", errors="ignore")
        sig = (len(txt), int(os.path.getmtime(GETDATA)))
        if sig == last_sig:
            time.sleep(interval)
            continue
        last_sig = sig

        p = read_pairs(txt)

        # Unidades: 1=MPH, 2=KPH
        speedo = fnum(p.get("SpeedoType")) or 2.0
        to_kph = 1.609344 if speedo == 1.0 else 1.0

        # Tiempos (opcional)
        sim_time = fnum(p.get("SimulationTime"))  # segundos
        tod = fnum(p.get("TimeOfDay"))  # segundos desde medianoche
        t_game = sim_time if sim_time is not None else tod

        # 1) Cambio de límite actual → speed_limit_change
        cur_kph = fnum(p.get("CurrentSpeedLimit"))
        if cur_kph is not None:
            cur_kph *= to_kph
            if last_current_kph is None:
                last_current_kph = cur_kph
            elif abs(cur_kph - last_current_kph) > 1e-3:
                emit(
                    {
                        "type": "speed_limit_change",
                        "prev": last_current_kph,
                        "next": cur_kph,
                        "t_game": t_game,
                        "source": "getdata_current",
                    }
                )
                last_current_kph = cur_kph

        # 2) Próximo límite + distancia → getdata_next_limit (sondear cada ~2s)
        nxt_kph = fnum(p.get("NextSpeedLimitSpeed"))
        nxt_dist = fnum(p.get("NextSpeedLimitDistance"))
        if nxt_kph is not None and nxt_dist is not None:
            nxt_kph *= to_kph
            # En algunos scripts: 0.0 / 10000 = "no hay próximo" (centinela)
            if (nxt_kph > 0.0) and (0.0 < nxt_dist < 9000.0):
                now = time.time()
                if (
                    (last_next_kph is None or abs(nxt_kph - last_next_kph) > 1e-3)
                    or (last_next_dist is None or abs(nxt_dist - last_next_dist) >= 25)
                    or (now - last_probe_ts) > 1.0
                ):
                    emit(
                        {
                            "type": "getdata_next_limit",
                            "kph": nxt_kph,
                            "dist_m": nxt_dist,
                            "t_game": t_game,
                            "source": "getdata_probe",
                        }
                    )
                    last_next_kph = nxt_kph
                    last_next_dist = nxt_dist
                    last_probe_ts = now

        time.sleep(interval)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=float, default=0.0, help="segundos; 0 = infinito")
    ap.add_argument("--interval", type=float, default=0.25, help="segundos entre lecturas")
    ap.add_argument("--quiet", action="store_true", help="menos logs")
    args = ap.parse_args()
    try:
        run(duration=args.duration, interval=args.interval, verbose=not args.quiet)
    except KeyboardInterrupt:
        print("[bridge] interrupción del usuario — saliendo limpio.")
        sys.exit(0)
