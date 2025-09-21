#!/usr/bin/env python3
"""Suggest control alias tokens from files in `profiles/`.

Scans JSON and CSV files under `profiles/`, extracts likely keys/column names,
prints a frequency-sorted list and optionally writes suggestions to an output JSON.

Example:
  python tools/suggest_control_aliases.py --profiles-dir profiles --out-file profiles/suggested_aliases.json

This script is readonly: it only proposes tokens and does not modify repository files.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable


def iter_profile_files(profiles_dir: str) -> Iterable[Path]:
    root = Path(profiles_dir)
    if not root.exists():
        return []
    for p in root.rglob("*"):
        if p.suffix.lower() in (".json", ".csv") and p.is_file():
            yield p


def extract_tokens_from_json(path: Path) -> Iterable[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    tokens = set()
    if isinstance(data, dict):
        for k, v in data.items():
            tokens.add(str(k))
            if isinstance(v, dict):
                for kk in v.keys():
                    tokens.add(str(kk))
    return tokens


def extract_tokens_from_csv(path: Path) -> Iterable[str]:
    try:
        with path.open("r", encoding="utf-8") as f:
            header = f.readline()
    except Exception:
        return []
    if not header:
        return []
    parts = [p.strip().strip('"') for p in header.split(",") if p.strip()]
    return [p for p in parts if p]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profiles-dir", default="profiles")
    parser.add_argument("--out-file", default=None)
    args = parser.parse_args()

    counts: Dict[str, int] = Counter()
    for path in iter_profile_files(args.profiles_dir):
        try:
            if path.suffix.lower() == ".json":
                toks = extract_tokens_from_json(path)
            else:
                toks = extract_tokens_from_csv(path)
        except Exception:
            toks = []
        for t in toks:
            counts[t] = counts.get(t, 0) + 1

    if not counts:
        print("No tokens found in", args.profiles_dir)
        return 0

    sorted_tokens = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    print("Found tokens (token:count):")
    for tok, c in sorted_tokens[:200]:
        print(f"  {tok}: {c}")

    if args.out_file:
        try:
            out_path = Path(args.out_file)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with out_path.open("w", encoding="utf-8") as f:
                json.dump({k: v for k, v in sorted_tokens}, f, indent=2, ensure_ascii=False)
            print("Wrote proposals to", str(out_path))
        except Exception as e:
            print("Failed to write out file:", e)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
