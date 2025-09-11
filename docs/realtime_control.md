# Control en tiempo real (SQLite / WAL)

Este documento resume la configuración y las banderas recomendadas para ejecutar el `control_loop` en tiempo real usando SQLite como fuente de telemetría.

Resumen rápido

- Fichero DB por defecto: `data/run.db` (modo WAL recomendado).
- El collector escribe tanto CSV append-only como intentos no bloqueantes de inserción en la DB.
- Comando de ejemplo:

```bash
python -m runtime.control_loop --source sqlite --db data/run.db \
  --events data/events.jsonl --profile profiles/BR146.json \
  --hz 5 --start-events-from-end --out data/ctrl_live.csv
```

Banderas importantes

- `--source {sqlite,csv}`: fuente preferida `sqlite`, `csv` fuerza lectura de CSV.
- `--db <path>`: ruta al fichero SQLite.
- `--start-events-from-end`: no reprocesar eventos antiguos; empezar desde el final.
- `--derive-speed-if-missing` (ON by default): derivar velocidad desde odómetro si falta `speed_kph`.
- `--no-csv-fallback`: deshabilita fallback automático a CSV cuando la DB está vacía.

Recomendaciones

- Usa WAL para la DB (`PRAGMA journal_mode=WAL`) para escrituras concurrentes.
- Asegura que el `collector` esté activo y escribiendo (ver `tools/db_check` y heartbeat `data/events/.collector_heartbeat`).
- Si migras históricos, usa `tools/migrate_run_csv_to_sqlite` antes de arrancar consumidores que dependan de SQLite.

Logs y debugging

- El `collector` no debe bloquearse por fallos en inserciones DB (catch/ignore): comprueba con `tools/db_check` si la DB está creciendo.
- Para seguir la salida en tiempo real usa `Get-Content -Tail -Wait` (PowerShell) o `tail -f` (Linux).
