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

Nota: después de instalar, es habitual que `pre-commit` modifique archivos (por ejemplo `ruff --fix` o `black`). Revise los cambios con `git status` y haga un commit adicional si el hook aplica correcciones automáticas.


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

Generar propuestas de aliases
-----------------------------
Si quieres identificar nombres y aliases usados en los perfiles existentes, hay una herramienta
ligera en `tools/suggest_control_aliases.py` que escanea `profiles/` y propone tokens frecuentes
que pueden ser candidatos a aliases.

Ejemplo (PowerShell):

```powershell
& ./.venv/Scripts/Activate.ps1
python tools/suggest_control_aliases.py --profiles-dir profiles --out-file profiles/suggested_aliases.json
```

El script imprimirá un resumen en stdout y, si se indica `--out-file`, guardará un JSON con
los tokens y sus conteos; no modifica archivos existentes — sólo propone. Revise `profiles/controls.py`
y aplique las propuestas manualmente (o úselo como base para una PR).

Diagnóstico y runbook
---------------------
Hemos incluido un runbook mínimo en `docs/EMERGENCY_RUNBOOK.md` y un script de diagnóstico
`scripts/diagnose_emergency.ps1` que recolecta los artefactos típicos usados por CI (`data/*.json`,
`data/rd_send.log`) y empaqueta la información para analizarla offline.

Ejemplo (PowerShell):

```powershell
& ./.venv/Scripts/Activate.ps1
# Ejecuta el script que recopila datos y crea un zip en la carpeta actual
python .\scripts\diagnose_emergency.ps1 -OutFile diagnostic-$(Get-Date -Format yyyyMMdd-HHmm).zip
```

Nota: en PowerShell puede ejecutar directamente `scripts/diagnose_emergency.ps1` si la política de
ejecución lo permite; el ejemplo anterior invoca el script de forma portable desde el entorno.

CI sugerido (resumen)
---------------------
- Se recomienda un workflow que ejecute: `ruff check . --fix` (o `ruff check .`), `flake8 .`, `pytest -q -o addopts=` y, opcionalmente, `mypy` en paths limitados.
- Ya existe un workflow de ejemplo en `.github/workflows/ci-flake8-safety.yml`.

### Comandos recomendados (PowerShell)

- Crear y activar entorno virtual, instalar deps:

```powershell
python -m venv .venv
& ./.venv/Scripts/Activate.ps1
python -m pip install -r requirements.txt -r requirements-dev.txt
```

- Formateo y checks rápidos:

```powershell
& ./.venv/Scripts/Activate.ps1
# ruff: checks + auto-fix
ruff check . --select F,E,W || ruff check . --fix

# black + isort (comprobar sin modificar automáticamente)
python -m black . --check
python -m isort . --check-only

# flake8
flake8 .
```

- Mypy (recomendado por paquete, evita falsos positivos globales):

```powershell
& ./.venv/Scripts/Activate.ps1
python -m mypy --ignore-missing-imports --follow-imports=silent ingestion runtime
```

- Tests:

```powershell
& ./.venv/Scripts/Activate.ps1
# Todos los tests (anula addopts de pytest.ini)
python -m pytest -q -o addopts=

# Solo safety (rápido antes de PRs)
python -m pytest -q -m safety -o addopts=
```

### Recomendaciones para CI

- Separar el job `safety-tests` que ejecute `python -m pytest -q -m safety -o addopts=` y aumente el timeout (p.ej. 30 min).
- Añadir un job `mypy` limitado a `ingestion` y `runtime` con `--check-untyped-defs` y fallar la build si se introducen errores nuevos.
- Subir artefactos (en caso de fallo) desde `data/control_status.json`, `data/rd_ack.json` y `data/rd_send.log` para diagnóstico.

Si quieres que yo genere un `workflow` de ejemplo con estos pasos lo puedo crear y abrir PR.

Contribuciones
--------------
- Cree PRs contra `main`. Añada tests para cambios de comportamiento importantes (especialmente en `ingestion/` y `runtime/`).
- Para cambios de seguridad/control: añada documentación en `docs/` y notifique a los mantenedores.

Notas finales
------------
- Mantenga líneas <= 120 caracteres para pasar `flake8`.
- Si quieres, puedo añadir o mejorar la plantilla de GitHub Actions para incluir un job `mypy` separado que sólo compruebe `ingestion/` y `tests/` para evitar falsos positivos por stubs externos.
