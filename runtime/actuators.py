from __future__ import annotations
from typing import Any, Dict, Tuple, Optional
import os
import inspect
import io
import importlib
from datetime import datetime

METHODS_THROTTLE = (
    "set_throttle",
    "write_throttle",
    "setThrottle",
    "setCombinedThrottle",
    "setCombinedThrottleBrake",
    "set_throttle_notch",
    "set_notch_throttle",
)
METHODS_BRAKE = (
    "set_brake",
    "write_brake",
    "setBrake",
    "setTrainBrake",
    "setCombinedBrake",
    "setDynamicBrake",
    "set_brake_notch",
    "set_notch_brake",
    "applyBrake",
    "apply_brake",
)


def _all_objs(env: Dict[str, Any]):
    for k, v in env.items():
        # ignorar módulos/funciones/clases
        if inspect.ismodule(v) or inspect.isfunction(v) or inspect.isclass(v):
            continue
        yield k, v


def scan_for_rd(locals_dict: Dict[str, Any], globals_dict: Dict[str, Any]) -> Tuple[Optional[Any], str]:
    """
    Busca el objeto RailDriver. Primero por alias comunes; luego escanea todo en
    busca de un objeto con método conocido.
    """
    for name in ("rd", "raildriver", "driver", "hw", "rd_client", "rdc"):
        obj = locals_dict.get(name) or globals_dict.get(name)
        if obj is not None:
            return obj, name
    # Escaneo por atributos de métodos
    for scope_name, env in (("locals", locals_dict), ("globals", globals_dict)):
        for name, obj in _all_objs(env):
            try:
                if any(hasattr(obj, m) for m in METHODS_THROTTLE + METHODS_BRAKE):
                    return obj, f"{scope_name}.{name}"
            except Exception:
                continue
    # Si no se encuentra nada, retornar explícitamente
    return None, ""


def load_rd_from_spec(spec: Optional[str]) -> Tuple[Optional[Any], str]:
    """
    Carga un objeto RD desde un spec 'modulo:atributo'.
    Si el atributo es callable, lo invoca sin args y usa su retorno.
    Devuelve siempre (obj_o_None, origen_str).
    """
    if not spec:
        return None, ""
    try:
        mod_name, attr = spec.split(":", 1)
        mod = importlib.import_module(mod_name)
        obj = getattr(mod, attr)
        if callable(obj):
            obj = obj()
        return obj, f"{mod_name}:{attr}"
    except Exception:
        # En cualquier error, devolvemos tupla nula y texto vacío
        return None, ""


def get_plan(
    locals_dict: Dict[str, Any], globals_dict: Dict[str, Any]
) -> Tuple[Optional[float], Optional[float], str, str]:
    """Recupera (throttle, brake) planificados sin referenciar nombres fijos, evitando F821."""
    cand_t = ("throttle_cmd", "throttle_plan", "cmd_throttle", "throttle")
    cand_b = ("brake_cmd", "brake_plan", "cmd_brake", "brake")
    t_src = b_src = ""
    t = next((locals_dict[n] for n in cand_t if n in locals_dict), None)
    if t is None:
        t = next((globals_dict[n] for n in cand_t if n in globals_dict), None)
        if t is not None:
            t_src = "globals"
    else:
        t_src = "locals"
    b = next((locals_dict[n] for n in cand_b if n in locals_dict), None)
    if b is None:
        b = next((globals_dict[n] for n in cand_b if n in globals_dict), None)
        if b is not None:
            b_src = "globals"
    else:
        b_src = "locals"
    return t, b, t_src, b_src


def _clamp01(x: Optional[float]) -> Optional[float]:
    if x is None:
        return None
    try:
        if x < 0:
            return 0.0
        if x > 1:
            return 1.0
        return float(x)
    except Exception:
        return None


def send_to_rd(rd_obj: Any, throttle: Optional[float], brake: Optional[float]) -> Tuple[bool, bool, str, str]:
    """
    Envía a RailDriver probando múltiples métodos.
    Devuelve: (throttle_sent, brake_sent, throttle_method, brake_method)
    Respeta TSC_BRAKE_INVERT=1 (convierte b -> 1-b).
    """
    thr_sent = brk_sent = False
    thr_m = brk_m = ""
    thr = _clamp01(throttle)
    brk = _clamp01(brake)
    # Invertir freno si así se usa la API del tren (1=libre, 0=aplicado)
    if os.getenv("TSC_BRAKE_INVERT", "0") in ("1", "true", "True"):
        if brk is not None:
            brk = 1.0 - brk
    # Combined method primero
    if hasattr(rd_obj, "setCombinedThrottleBrake"):
        try:
            rd_obj.setCombinedThrottleBrake(thr if thr is not None else 0.0, brk if brk is not None else 0.0)
            return (
                True if thr is not None else False,
                True if brk is not None else False,
                "setCombinedThrottleBrake",
                "setCombinedThrottleBrake",
            )
        except Exception:
            pass
    # Throttle
    if thr is not None:
        for m in METHODS_THROTTLE:
            if hasattr(rd_obj, m):
                try:
                    getattr(rd_obj, m)(thr)
                    thr_sent, thr_m = True, m
                    break
                except Exception:
                    continue
    # Brake
    if brk is not None:
        for m in METHODS_BRAKE:
            if hasattr(rd_obj, m):
                try:
                    getattr(rd_obj, m)(brk)
                    brk_sent, brk_m = True, m
                    break
                except Exception:
                    continue
    return thr_sent, brk_sent, thr_m, brk_m


def debug_trace(enabled: bool, msg: str) -> None:
    if not enabled:
        return
    line = f"{datetime.now().isoformat(timespec='seconds')} {msg}\n"
    print("[RD]", msg)
    try:
        os.makedirs("data", exist_ok=True)
        with io.open("data\\rd_send.log", "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass
