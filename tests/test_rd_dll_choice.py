from __future__ import annotations

import importlib
import struct


def is_64() -> bool:
    return 8 * struct.calcsize("P") == 8


def test_choose_correct_dll(tmp_path, monkeypatch):
    # Prepara un directorio de plugins temporal con la DLL "correcta" vacía
    dll_name = "RailDriver64.dll" if is_64() else "RailDriver.dll"
    (tmp_path / dll_name).write_bytes(b"")  # no se carga; solo comprobamos existencia
    monkeypatch.setenv("TSC_RD_DLL_DIR", str(tmp_path))

    # Importamos funciones helper sin inicializar RailDriver real
    mod = importlib.import_module("ingestion.rd_client")
    base = mod._resolve_plugins_dir()
    picked = mod._prepare_dll_search_path(base)
    assert picked.name == dll_name
