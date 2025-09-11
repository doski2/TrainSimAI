Control loop — flags y comportamiento por defecto
===============================================

Resumen rápido
- `--derive-speed-if-missing` está activado por defecto. Esto permite que, cuando una muestra no contiene `speed_kph`, el control intente derivar la velocidad a partir de la variación del odómetro entre muestras (odom_m). Esto salva muestras antiguas o entradas parciales.
- Si ejecutas con `--source sqlite` y la base de datos SQLite (`--db`) no contiene filas aún, el control intenta hacer fallback a la lectura directa del CSV (`data/runs/run.csv`) salvo que se pase `--no-csv-fallback`.

Flags relevantes
- `--source` ("sqlite" | "csv"): selecciona la fuente principal de telemetría. Por defecto `sqlite`.
- `--db <path>`: path a la base de datos SQLite (por defecto `data/run.db`).
- `--no-csv-fallback`: si se pasa, desactiva la lectura desde CSV cuando SQLite está vacío.
- `--derive-speed-if-missing`: habilita la derivación automática de `speed_kph` si falta (por defecto activado).
- `--no-derive-speed`: alternativa para desactivar la derivación si necesitas un comportamiento estricto.

Cómo funciona el fallback
1. Si `--source sqlite` y `--no-csv-fallback` no está activado, el control intentará leer filas nuevas desde la tabla `telemetry` de la DB.
2. Si la DB está vacía (`latest_since()` devuelve None), el control activará `use_csv = True` y pasará a leer la última fila completa del CSV con una función robusta (`tail_csv_last_row`).
3. Si `--no-csv-fallback` se especifica, el control esperará por la DB en su lugar y no intentará leer de CSV.

Notas operativas
- El comportamiento por defecto (derivar velocidad + permitir fallback a CSV) está pensado para tolerar ejecuciones donde la fuente SQLite se inicializa después del collector o cuando existen datos históricos en CSV.
- Si prefieres un comportamiento determinista y solo quieres leer desde SQLite, usa `--source sqlite --no-csv-fallback`.

Ejemplo de uso recomendado (modo robusto, por defecto):

```powershell
python -m runtime.control_loop --source sqlite --db data/run.db
```

Ejemplo estricto (solo SQLite):

```powershell
python -m runtime.control_loop --source sqlite --db data/run.db --no-csv-fallback --no-derive-speed
```
