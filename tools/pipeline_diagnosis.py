#!/usr/bin/env python3
"""
Script de diagnóstico para identificar por qué los datos están obsoletos
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import psutil


def check_trainsimai_processes() -> bool:
    """Verificar qué procesos de TrainSimAI están ejecutándose"""
    print("=== PROCESOS TRAINSIMAI ===")
    found = False

    for proc in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
        try:
            cmdline = " ".join(proc.info.get("cmdline") or [])
            if any(
                keyword in cmdline.lower()
                for keyword in [
                    "collector",
                    "control_loop",
                    "getdata_bridge",
                    "trainsimai",
                ]
            ):
                runtime = time.time() - (proc.info.get("create_time") or time.time())
                print(f"PID {proc.info.get('pid')}: {proc.info.get('name')}")
                print(f"  Comando: {cmdline}")
                print(f"  Ejecutándose desde: {runtime / 3600:.1f} horas")
                found = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if not found:
        print("❌ NO se encontraron procesos de TrainSimAI ejecutándose")
    return found


def check_key_files() -> None:
    """Verificar archivos clave del sistema"""
    print("\n=== ARCHIVOS CLAVE ===")

    files_to_check = [
        "data/run.db",
        "data/runs/run.csv",
        "data/lua_eventbus.jsonl",
        "data/events.jsonl",
        "data/ctrl_live.csv",
    ]

    for file_path in files_to_check:
        path = Path(file_path)
        if path.exists():
            stat = path.stat()
            size_mb = stat.st_size / (1024 * 1024)
            age_hours = (time.time() - stat.st_mtime) / 3600
            status = "🟢" if age_hours < 1 else "🟡" if age_hours < 24 else "🔴"
            print(
                f"{status} {file_path}: {size_mb:.2f} MB, modificado hace {age_hours:.1f}h"
            )
        else:
            print(f"❌ {file_path}: NO EXISTE")


def check_getdata_file() -> None:
    """Verificar el archivo GetData.txt de Train Simulator"""
    print("\n=== TRAIN SIMULATOR GETDATA ===")

    getdata_path = os.environ.get(
        "TSC_GETDATA_FILE",
        r"C:\Program Files (x86)\Steam\steamapps\common\RailWorks\plugins\GetData.txt",
    )

    if not getdata_path:
        print("❌ Variable TSC_GETDATA_FILE no definida")
        return

    path = Path(getdata_path)
    if path.exists():
        stat = path.stat()
        age_seconds = time.time() - stat.st_mtime
        status = "🟢" if age_seconds < 10 else "🟡" if age_seconds < 60 else "🔴"
        print(f"{status} GetData.txt: modificado hace {age_seconds:.1f}s")

        # Leer último contenido
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()[-200:]  # Últimos 200 chars
            print(f"Contenido reciente: ...{content}")
        except Exception as e:
            print(f"Error leyendo GetData.txt: {e}")
    else:
        print(f"❌ GetData.txt no encontrado en: {getdata_path}")


def check_collector_heartbeat() -> None:
    """Verificar el heartbeat del collector"""
    print("\n=== COLLECTOR HEARTBEAT ===")

    heartbeat_file = Path("data/events/.collector_heartbeat")
    if heartbeat_file.exists():
        stat = heartbeat_file.stat()
        age_seconds = time.time() - stat.st_mtime
        status = "🟢" if age_seconds < 30 else "🟡" if age_seconds < 300 else "🔴"
        print(f"{status} Heartbeat: hace {age_seconds:.1f}s")

        try:
            content = heartbeat_file.read_text(encoding="utf-8").strip()
            print(f"Contenido: {content}")
        except Exception as e:
            print(f"Error leyendo heartbeat: {e}")
    else:
        print("❌ No hay archivo de heartbeat del collector")


def suggest_fixes() -> None:
    """Sugerir soluciones basadas en el diagnóstico"""
    print("\n=== POSIBLES SOLUCIONES ===")
    print("1. Verificar que Train Simulator esté ejecutándose")
    print("2. Iniciar el collector manualmente:")
    print("   python -m runtime.collector --hz 10 --bus-from-start")
    print("3. Verificar la configuración TSC_GETDATA_FILE")
    print("4. Ejecutar el script completo:")
    print("   scripts\\tsc_real.bat")
    print("5. Verificar logs en data/ para errores específicos")


def main() -> None:
    print("🔍 DIAGNÓSTICO DEL PIPELINE TRAINSIMAI")
    print("=" * 50)

    processes_running = check_trainsimai_processes()
    check_key_files()
    check_getdata_file()
    check_collector_heartbeat()

    print("\n" + "=" * 50)
    if not processes_running:
        print("⚠️  DIAGNÓSTICO: No hay procesos TrainSimAI ejecutándose")
        print("   Los datos están obsoletos porque el sistema no está activo")
    else:
        print("ℹ️  DIAGNÓSTICO: Procesos ejecutándose pero datos obsoletos")
        print("   Posible problema en la cadena de datos")

    suggest_fixes()


if __name__ == "__main__":
    main()
