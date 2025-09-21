CONTRIBUTING
============

Resumen
-------
Este repositorio contiene módulos de control y herramientas de integración para el proyecto TrainSimAI.
Este documento recoge las comprobaciones básicas para desarrollar, probar y operar componentes relacionados con el controlador y el cliente RailDriver (RD).

Requisitos
---------
- Python 3.11
- Entorno virtual recomendado
- Dependencias: ver `requirements.txt` y `requirements-dev.txt`

Preparar entorno (PowerShell)
-----------------------------
```powershell
python -m venv .venv
& ./.venv/Scripts/Activate.ps1
python -m pip install -r requirements-dev.txt -r requirements.txt
```

Comprobaciones locales
----------------------
- Formateo/auto-fix con `ruff`:

```powershell
& ./.venv/Scripts/Activate.ps1
ruff check . --fix
```

- Revisar estilo con `flake8` (se espera 0 errores):

```powershell
& ./.venv/Scripts/Activate.ps1
flake8 .
```

- Ejecutar tests unitarios (suite completa):

```powershell
& ./.venv/Scripts/Activate.ps1
python -m pytest -q -o addopts=
```

- Ejecutar `mypy` (opcional / local)

```powershell
& ./.venv/Scripts/Activate.ps1
mypy --ignore-missing-imports ingestion runtime tests
```

Pre-commit (recomendado)
------------------------
Instale `pre-commit` y active los hooks para ejecutar `ruff`, `black` e `isort` localmente antes de los commits:

```powershell
& ./.venv/Scripts/Activate.ps1
python -m pip install pre-commit
pre-commit install
pre-commit run --all-files
```

Observabilidad (Prometheus)
---------------------------
- El cliente RD (`ingestion/rd_client.py`) puede exponer métricas Prometheus opcionalmente.
- Para activar el exporter HTTP, exporta la variable `TSC_PROMETHEUS_PORT` con un puerto disponible, por ejemplo `9188`:

```powershell
$env:TSC_PROMETHEUS_PORT = "9188"
python -m your_service_entrypoint
```

Si `prometheus_client` no está instalado, el exporter no se arrancará y el comportamiento es silencioso.

Operación de control / runbook mínimo
-----------------------------------
- Archivo de estado: `data/control_status.json` contiene propiedades útiles para diagnóstico: `last_command_time`, `last_command_value`, `last_ack_time`.
- ACKs: el runtime prueba un mecanismo simple basado en `data/rd_ack.json` para pruebas; en producción se recomienda confirmar por canal fiable (RPC/IPC).
- Watchdog de ACK: puede activarse en las opciones del cliente RD (ver `ingestion/rd_client.py`) y persistirá eventos en `data/control_status.json`.
- Emergency: si no se recibe ACK dentro del timeout configurado, el controlador entra en modo emergencia (freno al máximo). Para recovery manual: ajustar/borrar `data/control_status.json` y reiniciar el proceso de control.

Safety tests
------------
Los tests marcados con `@pytest.mark.safety` contienen escenarios sensibles para la seguridad
del controlador (ACKs faltantes, retries, rutas de emergencia). Estos tests se ejecutan en un job
separado en CI (`safety-tests`) con mayor timeout.

Buenas prácticas:
- Use `monkeypatch` para aislar dependencias hardware o IO.
- Keep tests small: un `safety` test debe validar una ruta crítica concreta (p. ej. que se llame
	`emergency_stop` si no hay confirmación de ACK).
- No añada sleeper largos en estos tests; si necesita simulación de tiempos, use time mocking.

Ejecutar localmente:

```powershell
& ./.venv/Scripts/Activate.ps1
python -m pytest -q -m safety
```

Para que CI ejecute estos tests, marque el test con `@pytest.mark.safety` y abra un PR; el job
`safety-tests` ejecutará sólo estos casos y fallará si alguno falla.

Control aliases y pruebas
-------------------------
- El mapeo canónico de controles está en `profiles/controls.py`.
- Para pruebas, `RDClient` acepta un mapping inyectado (o se puede apuntar a un archivo JSON referenciado por `TSC_CONTROL_ALIASES_FILE`). Esto facilita tests deterministas.

CI sugerido (resumen)
---------------------
- Se recomienda un workflow que ejecute: `ruff check . --fix` (o `ruff check .`), `flake8 .`, `pytest -q -o addopts=` y, opcionalmente, `mypy` en paths limitados.
- Ya existe un workflow de ejemplo en `.github/workflows/ci-flake8-safety.yml`.

Contribuciones
--------------
- Cree PRs contra `main`. Añada tests para cambios de comportamiento importantes (especialmente en `ingestion/` y `runtime/`).
- Para cambios de seguridad/control: añada documentación en `docs/` y notifique a los mantenedores.

Notas finales
------------
- Mantenga líneas <= 120 caracteres para pasar `flake8`.
- Si quieres, puedo añadir o mejorar la plantilla de GitHub Actions para incluir un job `mypy` separado que sólo compruebe `ingestion/` y `tests/` para evitar falsos positivos por stubs externos.
