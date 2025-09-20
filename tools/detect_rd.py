from __future__ import annotations
import argparse
import importlib
import inspect
from pathlib import Path
from typing import Any, Optional, Tuple, List
from runtime.actuators import METHODS_THROTTLE, METHODS_BRAKE

CANDIDATE_MODULES = [
    # Ajusta/añade si usas otro namespace
    "ingestion.rd_client",
    "ingestion.raildriver",
    "ingestion.rd",
    "runtime.raildriver",
    "runtime.rd",
    "plugins.raildriver",
    "bridge.raildriver",
    "raildriver",
    "rd",
]


def looks_like_rd(obj: Any) -> bool:
    try:
        return any(hasattr(obj, m) for m in (METHODS_THROTTLE + METHODS_BRAKE))
    except Exception:
        return False


def score_name(name: str) -> int:
    n = name.lower()
    score = 0
    for token in ("rd", "rail", "driver", "brake", "throttle"):
        if token in n:
            score += 1
    if n in ("rd", "raildriver", "driver"):
        score += 2
    return score


def try_import(mod_name: str):
    try:
        return importlib.import_module(mod_name)
    except Exception:
        return None


def best_candidate(extra_modules: List[str]) -> Tuple[Optional[str], str]:
    specs: List[Tuple[int, str, str]] = []  # (score, spec, kind)
    modules = []
    seen = set()
    for m in extra_modules or []:
        if m and m not in seen:
            modules.append(m)
            seen.add(m)
    for m in CANDIDATE_MODULES:
        if m not in seen:
            modules.append(m)
            seen.add(m)

    # 1) Objetos existentes en módulos
    for mod_name in modules:
        mod = try_import(mod_name)
        if not mod:
            continue
        for name, obj in vars(mod).items():
            if name.startswith("_"):
                continue
            # a) objeto directo con métodos de RD
            if looks_like_rd(obj):
                s = score_name(name) + 3  # objeto directo tiene prioridad
                specs.append((s, f"{mod_name}:{name}", "object"))
            # b) factoría sin parámetros que devuelva RD
            if inspect.isfunction(obj) and obj.__code__.co_argcount == 0:
                try:
                    inst = obj()
                    if looks_like_rd(inst):
                        s = score_name(name) + 2
                        specs.append((s, f"{mod_name}:{name}", "factory"))
                except Exception:
                    pass

    if not specs:
        return None, ""

    specs.sort(reverse=True, key=lambda x: x[0])
    _, spec, kind = specs[0]
    return spec, kind


def write_rd_provider(spec: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = (
        "@echo off\n"
        "REM Archivo generado por tools\\detect_rd.py\n"
        f'set "TSC_RD={spec}"\n'
        "echo [rd_provider] TSC_RD=%TSC_RD%\n"
    )
    path.write_text(content, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Detecta automaticamente el proveedor RailDriver (TSC_RD).")
    ap.add_argument("--modules", nargs="*", default=[], help="Modulos extra a probar (p.ej. paquete.subpaquete.modulo)")
    ap.add_argument("--write", action="store_true", help="Escribe scripts\\env\\rd_provider.bat con el spec detectado")
    args = ap.parse_args()

    spec, kind = best_candidate(args.modules)
    if not spec:
        print(
            "[detect_rd] No se encontro ningun objeto/factory RD visible. Pasa --modules paquete.modulo si lo conoces."
        )
        return 2

    print(f'[detect_rd] RECOMENDADO: set "TSC_RD={spec}"  ({kind})')
    if args.write:
        out = Path("scripts") / "env" / "rd_provider.bat"
        write_rd_provider(spec, out)
        print(f"[detect_rd] Escrito {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
