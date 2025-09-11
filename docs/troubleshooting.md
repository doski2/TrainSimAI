# Troubleshooting — checklist de errores comunes

Esta guía rápida agrupa problemas frecuentes y pasos para solucionarlos.

1) `ctrl_live.csv` no se actualiza
- Ejecuta `python -m tools.db_check --db data/run.db`. Si hay filas > 0, el problema está en el `control_loop` o en `--out` mal configurado. Si filas==0, migrar con `tools.migrate_run_csv_to_sqlite`.
- Verifica heartbeat del collector: `data/events/.collector_heartbeat`.
- Revisa variables de entorno: `RUN_CSV`, `RUN_CSV_PATH`, `RUN_EVT_PATH`.

2) PermissionError al escribir CSV en Windows
- Causa común: intentos de reemplazo atómico mientras otra proceso mantiene el handle abierto. Solución: el `collector` usa ahora CSV append-only; actualiza a la versión que contiene `runtime/csv_logger.py` y evita scripts que hagan `os.replace` sobre el CSV en caliente.

3) SQLite locked / operaciones bloqueadas
- Usa WAL y evita accesos largos dentro del colector. Recomendación: `PRAGMA journal_mode=WAL` y que los consumidores hagan lecturas rápidas (SELECT por `rowid`).

4) Delimitador incorrecto al hacer tail del CSV
- Si el CSV usa `;` o `	`, el tail puede mostrar filas que parezcan mal parseadas. Usa las herramientas `tools/migrate_run_csv_to_sqlite` que detectan delimitador.

5) Tests fallando en CI por `TSC_FAKE_RD`
- Asegura que en tu entorno de CI se exporte `TSC_FAKE_RD=1` (el workflow de ejemplo lo hace en la matriz). En Windows PowerShell usa `setx TSC_FAKE_RD 1` antes de llamar a Python si lo necesitas global.

6) `control_loop` sin datos al arrancar
- Inicia `collector` antes que `control_loop` o usa `tools/migrate_run_csv_to_sqlite` para precargar datos. Los scripts `scripts/tsc_sim.bat` y `scripts/tsc_real.bat` ya intentan ejecutar `tools.db_check` antes de lanzar el control.

7) Latencia inesperada en eventos
- Asegúrate de que el `bus` de eventos (LUA) no acumule backlog: usa `--start-events-from-end` para iniciar en la cola actual.

Si no resuelves, abre un issue con:
- Logs (salida del collector y control_loop)
- Resultado de `python -m tools.db_check --db data/run.db`
- Contenido de `data/ctrl_live.csv` (últimas 20 líneas)
