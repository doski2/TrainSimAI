from __future__ import annotations
import csv, json, os, sys
from collections import Counter, deque

CSV_PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join("data","runs","run.csv")
EVT_PATH = sys.argv[2] if len(sys.argv) > 2 else os.path.join("data","events","events.jsonl")

REQUIRED_SET = {
    "provider","product","engine","v_ms","v_kmh","t_wall",
    "VirtualBrake","TrainBrakeControl","VirtualEngineBrakeControl","Reverser",
    "BrakePipePressureBAR","TrainBrakeCylinderPressureBAR",
    "lat","lon","heading","gradient"
}
ALIAS_GROUPS = [
    ("Regulator","Throttle"),
    ("SpeedometerKPH","SpeedometerMPH")
]

def read_csv(path):
    if not os.path.exists(path):
        print(f"[CSV] No existe: {path}")
        return None, []
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f, delimiter=";")
        rows = list(r)
    return r.fieldnames, rows

def analyze_csv(fields, rows):
    print(f"[CSV] Filas: {len(rows)} | Columnas: {len(fields) if fields else 0}")
    if not rows:
        return
    missing = [k for k in REQUIRED_SET if k not in (fields or [])]
    # comprueba grupos alias: basta con que exista uno de cada grupo
    for a, b in ALIAS_GROUPS:
        if not ((a in (fields or [])) or (b in (fields or []))):
            missing.append(f"{a}|{b}")
    if missing:
        print(f"[CSV] Falta(n) columna(s) clave: {', '.join(sorted(set(missing)))}")
    engines = Counter((r.get("engine") or "").strip() for r in rows if r.get("engine"))
    if engines:
        top_engine, cnt = engines.most_common(1)[0]
        print(f"[CSV] Loco más frecuente: {top_engine} ({cnt} filas)")
    # tasa de muestreo aprox (últimas 200 filas con t_wall)
    tw = [float(r["t_wall"]) for r in rows[-200:] if r.get("t_wall")]
    if len(tw) >= 2:
        dur = max(tw) - min(tw)
        hz = (len(tw)-1)/dur if dur > 0 else 0.0
        print(f"[CSV] Tasa de muestreo ~ {hz:.2f} Hz en últimas {len(tw)} filas")
    # muestra breve
    print("[CSV] Muestra (últimas 2 filas):")
    for r in rows[-2:]:
        print({k: r.get(k) for k in ("v_kmh","Regulator","VirtualBrake","VirtualEngineBrakeControl","BrakePipePressureBAR")})

def analyze_events(path):
    if not os.path.exists(path):
        print(f"[EVT] No existe: {path}")
        return
    types = Counter()
    tail = deque(maxlen=5)
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = str(obj.get("type") or "unknown")
            types[t] += 1
            tail.append(obj)
    total = sum(types.values())
    print(f"[EVT] Total eventos: {total} | Por tipo: {dict(types)}")
    if tail:
        print("[EVT] Últimos eventos:")
        for o in tail:
            print(o)

def main():
    fields, rows = read_csv(CSV_PATH)
    analyze_csv(fields, rows)
    analyze_events(EVT_PATH)

if __name__ == "__main__":
    main()
