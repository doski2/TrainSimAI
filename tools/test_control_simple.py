#!/usr/bin/env python3
"""
Test simplificado del control loop para debugging
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path


def test_basic_functionality() -> None:
    """Test básico sin dependencias complejas"""
    print("=== TEST BÁSICO CONTROL LOOP ===")

    # Test 1: Imports básicos
    try:
        import sqlite3

        print("✅ sqlite3 importado correctamente")
    except ImportError as e:
        print(f"❌ Error importando sqlite3: {e}")
        assert False, f"Error importando sqlite3: {e}"

    # Test 2: Verificar archivo DB (resolver respecto a la raíz del repo para
    # evitar fallos cuando pytest cambia el working dir durante la ejecución)
    repo_root = Path(__file__).resolve().parent
    # tools/ is at repo_root / 'tools', así que la raíz del repo es parent
    repo_root = repo_root.parent
    db_path = repo_root / "data" / "run.db"
    if db_path.exists():
        print(f"✅ Base de datos encontrada: {db_path}")
        size_mb = db_path.stat().st_size / (1024 * 1024)
        print(f"   Tamaño: {size_mb:.2f} MB")
    else:
        print(f"❌ Base de datos no encontrada: {db_path}")
        assert False, f"Base de datos no encontrada: {db_path}"

    # Test 3: Conexión básica a SQLite
    try:
        with sqlite3.connect(db_path, timeout=5.0) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM telemetry")
            count = cursor.fetchone()[0]
            print(f"✅ Conexión SQLite exitosa: {count} filas")
    except Exception as e:
        print(f"❌ Error conectando a SQLite: {e}")
        assert False, f"Error conectando a SQLite: {e}"


def test_imports() -> None:
    """Test de imports problemáticos"""
    print("\n=== TEST DE IMPORTS ===")

    imports_to_test = [
        ("numpy", "numpy"),
        ("pandas", "pandas"),
        ("pathlib", "Path"),
        ("logging", "logging"),
        ("time", "time"),
        ("json", "json"),
        ("argparse", "argparse"),
    ]

    for module_name, import_name in imports_to_test:
        try:
            __import__(module_name)
            print(f"✅ {module_name} disponible")
        except ImportError:
            print(f"❌ {module_name} NO disponible")


def test_simple_control_loop() -> None:
    """Test simplificado del control loop"""
    print("\n=== TEST CONTROL LOOP SIMPLIFICADO ===")

    try:
        # Importar solo lo esencial
        import sqlite3
        from pathlib import Path

        # Clase minimalista para testing
        class SimpleControlLoop:
            def __init__(self, db_path):
                self.db_path = Path(db_path)
                self.running = False

            def read_last_telemetry(self):
                """Leer último dato de telemetría"""
                try:
                    with sqlite3.connect(self.db_path, timeout=2.0) as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            SELECT rowid, t_wall, odom_m, speed_kph
                            FROM telemetry
                            ORDER BY rowid DESC LIMIT 1
                        """)
                        row = cursor.fetchone()
                        if row:
                            return {"rowid": row[0], "t_wall": row[1], "odom_m": row[2], "speed_kph": row[3]}
                except Exception as e:
                    print(f"Error leyendo telemetría: {e}")
                return None

            def test_run(self, iterations=3):
                """Test básico de lectura"""
                print(f"Ejecutando {iterations} iteraciones de test...")

                for i in range(iterations):
                    data = self.read_last_telemetry()
                    if data:
                        age = time.time() - data["t_wall"] if data["t_wall"] else 9999
                        print(f"  Iteración {i + 1}: speed={data['speed_kph']} kph, age={age:.1f}s")
                    else:
                        print(f"  Iteración {i + 1}: Sin datos")
                    time.sleep(1)

        # Ejecutar test
        loop = SimpleControlLoop("data/run.db")
        loop.test_run(3)
        print("✅ Test básico completado")

    except Exception as e:
        print(f"❌ Error en test: {e}")
        assert False, f"Error en test: {e}"


def main() -> None:
    """Función principal de testing"""
    print("DIAGNÓSTICO CONTROL LOOP - TrainSimAI")
    print("=" * 50)

    # Configurar logging básico
    logging.basicConfig(level=logging.INFO)

    # Ejecutar tests
    basic_ok = True
    try:
        test_basic_functionality()
    except AssertionError as e:
        basic_ok = False
        print(f"\n❌ Tests básicos fallaron: {e}")

    test_imports()

    if basic_ok:
        try:
            test_simple_control_loop()
        except AssertionError as e:
            print(f"\n❌ Test simplificado falló: {e}")
    else:
        print("\n❌ Tests básicos fallaron - no se puede continuar")

    print("\n" + "=" * 50)
    if basic_ok:
        print("RESULTADO: Tests básicos EXITOSOS")
        print("SIGUIENTE PASO: Probar control_loop completo después de arreglar argparse")
    else:
        print("RESULTADO: Hay problemas básicos que resolver primero")


if __name__ == "__main__":
    # Argparse simplificado para evitar el error
    parser = argparse.ArgumentParser(description="Test simplificado de control loop")
    parser.add_argument("--verbose", action="store_true", help="Modo verboso")

    try:
        args = parser.parse_args()
        main()
    except Exception as e:
        print(f"Error en argparse: {e}")
        # Ejecutar sin argumentos si falla
        main()
