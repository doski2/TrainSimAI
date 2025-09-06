Vendor assets
=============

Este directorio está pensado para binarios/activos grandes que NO deben versionarse en Git (DLLs, instaladores, manuales, etc.).

TSClassic Raildriver and Joystick Interface
------------------------------------------

- Origen: software de RailDriver / TS Classic (Steam). Consulta su licencia y Términos en su fuente original.
- Recomendado: NO incluir estos binarios en el repositorio. En su lugar:
  - Usa la instalación oficial en Steam: `.../Steam/steamapps/common/RailWorks/plugins`.
  - Configura la variable de entorno `RAILWORKS_PLUGINS` apuntando a esa carpeta para que el loader elija la DLL correcta.
    Ejemplo (PowerShell):
    `$env:RAILWORKS_PLUGINS = 'C:\\Program Files (x86)\\Steam\\steamapps\\common\\RailWorks\\plugins'`

Opcional
--------

Si prefieres tener una copia local aquí (NO versionada), puedes colocar dentro de `vendor/` la carpeta del interfaz (p. ej., `TSClassic Raildriver and Joystick Interface V3.3.0.9/`). Asegúrate de que `.gitignore` la excluye.

Notas técnicas
--------------

- El código ya soporta `RAILWORKS_PLUGINS` (ver `ingestion/rd_client.py`) y autodetección por registro de Steam.
- En Python 64‑bit se carga `RailDriver64.dll`; en 32‑bit, `RailDriver.dll`.

