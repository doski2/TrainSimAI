# Higiene de datos (`data/`)

Directrices rápidas sobre qué archivos van en `data/` y qué se debe ignorar en VCS.

Qué va en `data/` (local, no versionar)
- `data/runs/run.csv` — CSV append-only del collector.
- `data/run.db` — SQLite RunStore (WAL), almacenamiento local de telemetría.
- `data/ctrl_live.csv` — CSV de salida usado por el control en tiempo real.
- `data/events.jsonl` y `data/lua_eventbus.jsonl` — colas de eventos locales.

Qué ignorar / no commitear
- Archivos binarios, dumps de pruebas y plots (`plot_*.png`, `TEMP_*`).
- Bases de datos locales (`data/run.db`) y directorios de ejecución.

Recomendación `.gitignore` mínima (ya presente en repo):

```
# datos locales
data/*.db
data/*.png
data/*.csv
data/events/*.jsonl
TEMP_*
plot_*.png
```

Buenas prácticas
- Guarda sólo datos reproducibles o muestras pequeñas para tests; no subas runs completos al repo.
- Usa `tools/migrate_run_csv_to_sqlite` para crear DB desde CSV si necesitas reproducir análisis localmente.
