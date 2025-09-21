# TrainSimAI (TSC)

[![CI](https://github.com/doski2/TrainSimAI/actions/workflows/ci-mypy-safety.yml/badge.svg)](https://github.com/doski2/TrainSimAI/actions/workflows/ci-mypy-safety.yml)

Autopiloto/analizador para **Train Simulator Classic** (Windows, Python 64-bit).
Pipeline: **GetData → Bus LUA → Collector → Distancia próximo límite → Frenada v0 (offline/online)** con trazas y tests.
See `CONTRIBUTING.md` for developer setup, linters, and CI details.

## Operación

Sección rápida para ejecutar y diagnosticar la aplicación en entornos de desarrollo y staging.

- Variables de entorno importantes:
    - `TSC_RD` - dirección/endpoint del rail driver (p.ej. `tcp://127.0.0.1:5555`).
    - `TSC_PROFILE` - perfil de vehículo a usar (nombre de archivo en `profiles/`).
    - `TSC_PROMETHEUS_PORT` - si está definida, habilita un exporter Prometheus en el puerto indicado para exponer métricas internas (p.ej. `8000`).

- Comandos útiles:
    - Ejecutar la suite de tests completa:
        - `python -m pytest -q`
    - Ejecutar solo tests de seguridad `safety` (útil localmente antes de abrir PRs):
        - `python -m pytest -q -m safety`
    - Lanzar el lazo de control en modo simulación (usa RD fake en `ingestion/rd_fake.py`):
        - `python -m runtime.control_loop`

- Archivos y artefactos relevantes (carpeta `data/`):
    - `data/control_status.json` - estado actual de los comandos de control y reintentos; útil para auditoría y debugging.
    - `data/rd_ack.json` - últimos ACK recibidos del rail driver (si procede).
    - `data/rd_send.log` - registro de intentos/sets enviados al rail driver.

- Observability / métricas:
    - Si `prometheus_client` está instalado y `TSC_PROMETHEUS_PORT` definido, el proceso expondrá métricas que incluyen contadores para ACKs, retries y eventos de emergencia. Estas métricas facilitan alerting y dashboards.

- Depuración rápida en Windows PowerShell:
    - Ejecutar linters y formateo:
        - `python -m ruff check . --select F,E,W`
        - `python -m black . --check`
    - Ejecutar mypy para `ingestion` y `runtime`:
        - `python -m mypy --ignore-missing-imports --follow-imports=silent ingestion runtime`

Si necesitas más detalles operativos (runbook para emergencias, diagnóstico automatizado y procesos de recuperación), ver `docs/` donde se pondrá `EMERGENCY_RUNBOOK.md` pronto.

If you want, actualizo `tsc_sim.bat` para que convenga explícitamente `--no-csv-fallback` o añadir logging más verboso al arranque del `control_loop`.


## TL;DR (rápido)

### Windows (.bat)
- **Simulado (sin juego):** `scripts\tsc_sim.bat`
- **Con juego (GetData):** `scripts\tsc_real.bat`
> Abren bridge/collector/control y un *tail* del CSV.

> Desde ahora, el **control** lee de **SQLite** (`data/run.db`, WAL) y mantiene **fallback a CSV** si la DB aún no tiene filas.

```powershell
# 0) Entorno
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 1) Bridge (GetData → bus)
$env:TSC_GETDATA_FILE="C:\\Program Files (x86)\\Steam\\steamapps\\common\\RailWorks\\plugins\\GetData.txt"
python -m ingestion.getdata_bridge

# 2) Collector (normaliza y sella t_wall/odom)
$env:TSC_FAKE_RD='1'
python -m runtime.collector --hz 10 --bus-from-start

# 3) Control (SQLite + fallback)
python -m runtime.control_loop --source sqlite --db data\run.db --events data\events.jsonl --profile profiles\BR146.json --hz 5 --start-events-from-end --out data\ctrl_live.csv

### Flags clave
- `--source {sqlite,csv}`: fuente de datos (por defecto: `sqlite`).
- `--db data\run.db`: ruta DB SQLite (WAL).
- `--run data\runs\run.csv`: CSV de respaldo.
- `--derive-speed-if-missing` (ON por defecto): deriva velocidad de odómetro si falta `speed_kph`.
- `--no-csv-fallback`: desactiva el fallback automático a CSV.
```

### Uso en tiempo real (con SQLite)

Ejemplo de ejecución en tiempo real (el control intentará leer desde SQLite y, por compatibilidad, hará fallback automático a CSV si SQLite está vacío):

```bash
# tiempo real (con fallback a CSV automático)
python -m runtime.control_loop --source sqlite --db data/run.db \
    --events data/events.jsonl --profile profiles/BR146.json \
    --hz 5 --start-events-from-end --out data/ctrl_live.csv
```

Explicación de flags relevantes:

- `--source {sqlite,csv}`
    - `sqlite`: el control leerá la última telemetría desde la base de datos SQLite indicada con `--db` (método preferido; usa `RunStore`).
    - `csv`: fuerza la lectura desde el CSV de salida (`--out`), útil para entornos simples o debugging.

- `--db <path>`
    - Ruta al fichero SQLite (por ejemplo `data/run.db`). Usado solo cuando `--source sqlite`.

- `--start-events-from-end`
    - Inicia la lectura del fichero de eventos (`--events`) desde el final en lugar de procesar todo el historial. Muy útil para retomar una sesión en tiempo real y evitar reprocesar todo el historial.

- `--derive-speed-if-missing` (por defecto: ON)
    - Si la muestra entrante no trae `speed_kph`, el control intentará derivar la velocidad a partir de la diferencia del odómetro entre muestras sucesivas. Esto está activado por defecto; puede desactivarse con `--no-derive-speed`.

Fallback a CSV
- Por compatibilidad y robustez en arranques, si `--source sqlite` está seleccionado pero la base de datos está vacía o inaccesible, el control puede caer automáticamente al modo CSV (leer la última línea del CSV `--out`). Este comportamiento se puede desactivar con la opción `--no-csv-fallback` si se desea un fallo explícito en ausencia de datos en la base.

Nota: el `collector` escribe tanto un CSV append-only como intentos no bloqueantes de insertar en SQLite (WAL). Esto evita problemas de bloqueo en Windows y permite la migración progresiva de consumidores al `RunStore`.

### Troubleshooting — `ctrl_live.csv` vacío

Si el fichero `--out` (por ejemplo `data/ctrl_live.csv`) está vacío o no se actualiza, sigue estos pasos:

1) Comprobar si la base de datos SQLite tiene filas:

PowerShell:

```powershell
python -m tools.db_check --db data\run.db
```

Linux / Git Bash:

```bash
python -m tools.db_check --db data/run.db
```

Salida esperada (ejemplo cuando hay datos):

```
[db_check] filas en telemetry: 10126
[db_check] última fila: (10126, 1757536887.6454296, 40790.31661716371, 40.79)
```

Si `filas en telemetry: 0` → migrar desde el CSV histórico (si lo tienes):

PowerShell / Bash:

```powershell
python -m tools.migrate_run_csv_to_sqlite --in data/runs/run.csv --out data/run.db
```

2) Confirmar que el `collector` activo está insertando en SQLite

- Verifica el heartbeat del collector (archivo creado por el collector):

PowerShell:

```powershell
if (Test-Path data\events\.collector_heartbeat) { Get-Content data\events\.collector_heartbeat } else { Write-Host 'No hay heartbeat (collector no activo)' }
```

También puedes observar si el número de filas en la DB aumenta en tiempo real (ejecuta en bucle):

PowerShell (comprobar cada 2s):

```powershell
while ($true) { python -m tools.db_check --db data\run.db; Start-Sleep -s 2 }
```

Linux / Git Bash (equivalente):

```bash
watch -n 2 "python -m tools.db_check --db data/run.db"
```

Si las filas aumentan con el tiempo, el collector está insertando correctamente en SQLite.

3) Comando de `tail` y ejemplos de salida esperada

PowerShell (últimas 5 líneas del CSV):

```powershell
Get-Content data\ctrl_live.csv -Tail 5
```

Linux / Git Bash:

```bash
tail -n 5 data/ctrl_live.csv
```

Salida tipo (cabecera + una fila de ejemplo):

```
t_wall,time_ingame_h,time_ingame_m,time_ingame_s,lat,lon,heading,gradient,v_ms,v_kmh,odom_m,...
1757536887.6454296,12,34,56,51.5074,-0.1278,180,0.0,11.33,40.79,40790.3166,...
```

Si el CSV sigue sin actualizarse pero la DB sí recibe filas, revisa que el proceso del collector no esté lanzado con otro `CSV_PATH` (variable de entorno `RUN_CSV_PATH`) o que `--out` usado por el control no sea un fichero distinto.

Si necesitas ayuda para depurar procesos en Windows (identificar qué proceso es el collector), puedo añadir comandos PowerShell sugeridos para listarlo y su línea de comandos.

### Guía rápida `.BAT` — `scripts\tsc_sim.bat` y `scripts\tsc_real.bat`

Dentro de `scripts/` hay atajos para arrancar la pila en Windows. Resumen del comportamiento y cómo usarlos:

- `scripts\tsc_sim.bat` (modo simulado)
    - Variables por defecto: `TSC_FAKE_RD=1`, `RUN_CSV=data\runs\run.csv`, `EVENTS=data\events.jsonl`, `PROFILE=profiles\BR146.json`, `OUT=data\ctrl_live.csv`.
    - Orden de ventanas/procesos lanzados:
        1. `collector` (simulado) — normaliza telemetría y escribe CSV + SQLite.
        2. `tools.db_check` — chequeo rápido de `data\run.db` antes de arrancar control (impide arrancar control vacio si DB está a 0 filas).
        3. `control_loop` — en modo `--source sqlite --db data/run.db` con `--start-events-from-end`.
        4. `tail` de `data\ctrl_live.csv` en una ventana PowerShell (Get-Content -Tail -Wait).

- `scripts\tsc_real.bat` (con juego / GetData)
    - Similar a `tsc_sim.bat` pero además arranca `ingestion.getdata_bridge` para leer `GetData.txt` del juego.
    - No establece `TSC_FAKE_RD` (usa el backend real RDClient). Asegúrate de ajustar `TSC_GETDATA_FILE` en el script si tu ruta es distinta.

Detalles y notas:
- `TSC_FAKE_RD=1` (en `tsc_sim.bat`) obliga a usar el backend simulado para pruebas sin hardware; útil para debugging y CI locales.
- La ventana de `tail` abre una PowerShell con `Get-Content -Tail <N> -Wait` para seguir el CSV en tiempo real.
- Si modificas `--out` u `RUN_CSV`, actualiza la variable correspondiente en el `.bat` para que el `tail` y `control` usen el mismo fichero.

Si quieres, actualizo `tsc_sim.bat` para que convenga explícitamente `--no-csv-fallback` o añadir logging más verboso al arranque del `control_loop`.


## Estructura
```
ingestion/   # Bridges y captura (GetData → bus LUA)
runtime/     # Collector y lógica online (PID/frenada en módulos dedicados)
tools/       # Utilidades offline (distancias, merge, plot)
tests/       # Unitarios/integ.
docs/        # Documentación (frenada v0, limpieza, guías)
profiles/    # (Opcional) perfiles por locomotora (A, márgenes, etc.)
data/        # Artefactos locales (no versionar)
```

## Requisitos
- Windows x64, Python 3.10+ (recomendado 3.11/3.12).
- `pip install -r requirements.txt`

## Variables clave
- `TSC_GETDATA_FILE` → ruta a `GetData.txt` de RailWorks.
- `LUA_BUS_PATH` → ruta de salida del bus (por defecto `data/lua_eventbus.jsonl`).
- `TSC_FAKE_RD=1` → backend simulado para pruebas sin hardware.

## Operaciones / Healthchecks (SQLite)

Para entornos de producción o integración continua es útil controlar parámetros de SQLite y disponer de un healthcheck sencillo.

- Variables de entorno para tunear SQLite (coleccionista / RunStore):
    - `TSC_DB_BUSY_MS` — timeout en milisegundos que se pasa a `PRAGMA busy_timeout`. Ejemplo: `5000` (5s).
    - `TSC_DB_SYNCHRONOUS` — valor de `PRAGMA synchronous` como entero (`0|1|2|3`) o texto (`OFF|NORMAL|FULL`). Ejemplo: `NORMAL` o `2`.

    Estas variables se leen por `runtime.collector` y se pasan al constructor de `RunStore` si están definidas. Si no se definen, se usan los valores por defecto del código.

- Script de comprobación de salud: `scripts/db_health.py`
 

## Prometheus wrapper & systemd

Se proporcionan ejemplos de unidades `systemd` en `scripts/systemd/`:

- `db_health.service` / `db_health.timer`: ejecuta `scripts/db_health.py` periódicamente (ejemplo 1m).
- `prom_wrapper.service` / `prom_wrapper.timer`: ejecuta `scripts/db_health_prometheus.py` cada 15s y escribe `/var/lib/node_exporter/textfile_collector/trainsim_db.prom`.

Instalación (ejemplo Debian/Ubuntu):

```bash
sudo cp scripts/systemd/*.service /etc/systemd/system/
sudo cp scripts/systemd/*.timer /etc/systemd/system/
sudo mkdir -p /var/lib/node_exporter/textfile_collector
sudo chown -R prometheus:prometheus /var/lib/node_exporter/textfile_collector
sudo systemctl daemon-reload
sudo systemctl enable --now db-health.timer prom_wrapper.timer
```

Ajusta `User=`/`Group=` y `ExecStart=` en los ficheros si tu instalación difiere.

    Uso rápido (PowerShell):

    ```powershell
    # comprobar DB y obtener JSON resumen
    python .\scripts\db_health.py data\run.db --pretty

    # exit codes:
    # 0 = OK (connect + write ok)
    # 1 = warning (connect ok, write failed)
    # 2 = error (connect failed)
    ```

    Ejemplo en una tarea de monitorización (systemd/cron/checker): ejecutar el script y usar el exit code para alertas.

Nota: `scripts/db_health.py` utiliza `storage.db_check.run_all_checks()` que devuelve pragmas informativos y comprueba si se puede adquirir un bloqueo de escritura (mediante `BEGIN IMMEDIATE` + rollback) para validar problemas de contención.

## Calidad
```powershell
pytest -q
ruff check .
# opcional
mypy runtime tools --strict
```

## Documentación
- [Frenada v0 (especificación y uso)](docs/frenada_v0.md)
- [Higiene del repositorio / datos y .gitignore](docs/repo_limpieza.md)
- [Índice de documentación](docs/README.md)

## Contribuciones (patches mínimos)
> Propón cambios **pequeños** y enfocados, con tests. Evita reescrituras masivas.
Incluye diffs por archivo (`*** Begin Patch …`) y separa archivos nuevos.
