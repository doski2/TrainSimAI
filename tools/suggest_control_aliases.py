"""Scan `profiles/*.json` and suggest control aliases for `profiles.controls`.

Produces `artifacts/controls-suggestions.json` with counts and example profiles.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PROFILES_DIR = ROOT / "profiles"
OUT_DIR = ROOT / "artifacts"
OUT_FILE = OUT_DIR / "controls-suggestions.json"


def iter_profile_keys(p: Path):
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return

    stack = [data]
    while stack:
        obj = stack.pop()
        if isinstance(obj, dict):
            for k, v in obj.items():
                yield k
                if isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(obj, list):
            for v in obj:
                if isinstance(v, (dict, list)):
                    stack.append(v)


def looks_like_control_key(k: str) -> bool:
    # Heurística: no keys de metadatos cortos, y deben contener letters
    if not isinstance(k, str):
        return False
    k = k.strip()
    if len(k) < 3 or len(k) > 60:
        return False
    low = k.lower()
    if low in ("name", "description", "provider", "product", "engine", "version"):
        return False
    # must contain at least one ASCII letter
    if not re.search(r"[a-zA-Z]", k):
        return False
    # reject deeply generic-looking keys
    if re.match(r"^[0-9]+$", k):
        return False
    return True


def main() -> int:
    OUT_DIR.mkdir(exist_ok=True)
    counts = Counter()
    profiles_by_alias = defaultdict(list)
    for p in sorted(PROFILES_DIR.glob("*.json")):
        for k in set(iter_profile_keys(p)):
            if looks_like_control_key(k):
                counts[k] += 1
                profiles_by_alias[k].append(p.name)

    # Build suggestions: map alias -> metadata
    suggestions = {}
    for alias, cnt in counts.most_common():
        suggestions[alias] = {
            "count": cnt,
            "profiles": profiles_by_alias.get(alias, [])[:20],
        }

    OUT_FILE.write_text(json.dumps({"suggestions": suggestions}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {OUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
