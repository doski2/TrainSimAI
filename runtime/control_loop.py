from __future__ import annotations

from tools.online_control import main as _main

"""
Compat: wrapper para ejecutar el control online como runtime.control_loop
Delegamos en tools.online_control.main
"""


def main() -> None:
    _main()


if __name__ == "__main__":
    main()
