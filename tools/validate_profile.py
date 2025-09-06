from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED_TOP = {"meta", "speed", "controls"}
REQUIRED_SPEED = {"sensor", "unit"}
REQUIRED_SENSOR = {"name", "min", "max"}


def fail(msg: str) -> None:
    print(f"[perfil] ERROR: {msg}", file=sys.stderr)
    sys.exit(2)


def main() -> None:
    if len(sys.argv) != 2:
        print("Uso: python tools/validate_profile.py profiles/DTG.Dresden.DB_BR146.2.json")
        sys.exit(1)
    path = Path(sys.argv[1])
    if not path.exists():
        fail(f"No existe {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    top_keys = set(data.keys())
    missing = REQUIRED_TOP - top_keys
    if missing:
        fail(f"Faltan claves top: {sorted(missing)}")

    speed = data["speed"]
    if not REQUIRED_SPEED.issubset(speed.keys()):
        fail(f"speed requiere {sorted(REQUIRED_SPEED)}")
    if not REQUIRED_SENSOR.issubset(speed["sensor"].keys()):
        fail(f"speed.sensor requiere {sorted(REQUIRED_SENSOR)}")

    # Reglas suaves
    if speed.get("unit") not in {"kmh", "mph"}:
        print("[perfil] aviso: speed.unit no es kmh/mph")

    controls = data["controls"]
    must_have = ["throttle", "train_brake", "reverser"]
    for k in must_have:
        if k not in controls:
            fail(f"Falta control obligatorio: {k}")

    print("[perfil] OK:", path.name)
    print(" - provider:", data["meta"].get("provider"))
    print(" - engine:", data["meta"].get("engine"))
    print(
        " - speed sensor:",
        speed["sensor"]["name"],
        f"[{speed['sensor']['min']},{speed['sensor']['max']}]",
    )


if __name__ == "__main__":
    main()

