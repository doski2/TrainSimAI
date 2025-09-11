from __future__ import annotations

import argparse
import sys
from typing import Optional

try:
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover - best-effort plotting
    plt = None

from runtime.braking_era import compute_target_speed_kph_era, EraCurve
from runtime.profiles import load_braking_profile, load_profile_extras
from runtime.braking_v0 import BrakingConfig


def main(v_now: float, limit: float, dmax: float, step: float, profile: str) -> None:
    # Cargar perfil
    try:
        cfg: BrakingConfig = load_braking_profile(profile)
    except Exception:
        cfg = BrakingConfig()

    extras = load_profile_extras(profile) if profile else {}
    era_csv: Optional[str] = extras.get("era_curve_csv") if isinstance(extras, dict) else None
    if not era_csv:
        print("Profile does not include 'era_curve_csv' in extras", file=sys.stderr)
        return

    curve = EraCurve.from_csv(era_csv)

    ds = [i * step for i in range(int(dmax / step) + 1)]
    vs = []
    for d in ds:
        v, _ = compute_target_speed_kph_era(v_now, limit, d, curve, cfg=cfg)
        vs.append(v)

    if plt is None:
        print("matplotlib not available; printing values instead")
        for d, v in zip(ds, vs):
            print(d, v)
        return

    plt.figure()
    plt.plot(ds, vs, label="v_target_kph")
    plt.axhline(limit, linestyle="--", color="red", label="limit_kph")
    plt.title(f"Curva v0 – v_now={v_now} kph, limit={limit} kph")
    plt.xlabel("dist_next_limit_m")
    plt.ylabel("v_target_kph")
    plt.grid(True)
    plt.legend()
    plt.show()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--v-now", type=float, default=120.0)
    ap.add_argument("--limit", type=float, default=80.0)
    ap.add_argument("--dmax", type=float, default=1500.0)
    ap.add_argument("--step", type=float, default=10.0)
    ap.add_argument("--profile", default="profiles/BR146.json")
    args = ap.parse_args()
    main(args.v_now, args.limit, args.dmax, args.step, args.profile)
