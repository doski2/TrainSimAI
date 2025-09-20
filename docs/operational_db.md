# Operaciones: DB healthchecks e integración

Este documento muestra ejemplos operativos para ejecutar los healthchecks de SQLite añadidos en `scripts/db_health.py`, y cómo integrarlos en tooling de monitorización (systemd, cron, Prometheus). Está pensado como guía práctica para operadores.

Contenido

- Ejecutable: `scripts/db_health.py` (JSON + exit code)
- Exit codes: `0` OK, `1` warning (no write), `2` error (no connect)
- Variables de entorno útiles: `TSC_DB_BUSY_MS`, `TSC_DB_SYNCHRONOUS`

---

## Ejecución manual

PowerShell (Windows):

```powershell
python .\scripts\db_health.py data\run.db --pretty
```

Linux / Bash:

```bash
python ./scripts/db_health.py data/run.db --pretty
```

Salida: JSON con campos `connect`, `can_write`, `pragmas` y `timestamp`.

---

## systemd (Linux) — servicio de comprobación periódica

Ejemplo de unidad `systemd` que ejecuta el script cada minuto y registra la salida en `journalctl`. Crea dos archivos: `db-health.service` y `db-health.timer`.

`/etc/systemd/system/db-health.service`

```ini
[Unit]
Description=TrainSimAI DB health check

[Service]
Type=oneshot
ExecStart=/usr/bin/env python /opt/TrainSimAI/scripts/db_health.py /var/lib/trainsimai/data/run.db --pretty
User=trainsim
Group=trainsim
Nice=10
AmbientCapabilities=
```

`/etc/systemd/system/db-health.timer`

```ini
[Unit]
Description=Run TrainSimAI DB health every minute

[Timer]
OnBootSec=1min
OnUnitActiveSec=1min

[Install]
WantedBy=timers.target
```

Activación:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now db-health.timer
```

Revisión rápida:

```bash
journalctl -u db-health.service -f
systemctl status db-health.timer
```

Interpretación de resultados: el exit code aparece en `systemctl status` y la salida JSON en journal.

---

## Cron (alternativa simple)

Entrada de crontab (edita con `crontab -e` del usuario apropiado):

```cron
* * * * * cd /opt/TrainSimAI && /usr/bin/env python scripts/db_health.py data/run.db --pretty > /var/log/trainsimai/db_health.json 2>&1
```

En este ejemplo se vuelca la salida en `/var/log/trainsimai/db_health.json`. Un analizador o un `logrotate` pueden gestionar la rotación.

---

## Integración con Prometheus (Node Exporter textfile collector)

Node Exporter debe tener el textfile collector activado y leer el directorio indicado (`/var/lib/node_exporter/textfile_collector` en ejemplo).

---

## Instalación de los servicios systemd (db_health + prom_wrapper)

Ejemplo de pasos para desplegar las unidades `db-health` y el wrapper Prometheus `prom_wrapper` en un servidor Linux (Debian/Ubuntu):

```bash
# 1) Copiar unidades de ejemplo al sistema
sudo cp scripts/systemd/db_health.service /etc/systemd/system/db-health.service
sudo cp scripts/systemd/db_health.timer /etc/systemd/system/db-health.timer
sudo cp scripts/systemd/prom_wrapper.service /etc/systemd/system/prom_wrapper.service
sudo cp scripts/systemd/prom_wrapper.timer /etc/systemd/system/prom_wrapper.timer

# 2) Crear directorio para Node Exporter textfile collector y fijar permisos
sudo mkdir -p /var/lib/node_exporter/textfile_collector
sudo chown -R prometheus:prometheus /var/lib/node_exporter/textfile_collector
sudo chmod 750 /var/lib/node_exporter/textfile_collector

# 3) Ajustar rutas en las unidades si tu instalación difiere (DB path, usuario, install path)

# 4) Recargar systemd y habilitar timers
sudo systemctl daemon-reload
sudo systemctl enable --now db-health.timer prom_wrapper.timer
```

Notas:
- Las unidades de ejemplo asumen que existe un usuario `prometheus` que puede escribir el directorio textfile. Si tu instalación usa otro usuario, ajusta `User=` y `Group=` en las unidades.
- `prom_wrapper.service` está configurado como `Type=oneshot` y se ejecuta periódicamente por su `timer` cada 15s (ajusta `OnUnitActiveSec` según tu necesidad y la frecuencia de scrapes de Prometheus).
- Si tu `RunStore` se encuentra en otra ruta, actualiza la ruta `ExecStart=` en `prom_wrapper.service`.

1. Ejecutar un wrapper que llame a `scripts/db_health.py` y traduzca su resultado a métricas Prometheus en formato textfile.
2. El Node Exporter leerá esos ficheros y Prometheus los scrapea.

Ejemplo de wrapper `scripts/db_health_prometheus.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

DB=${1:-data/run.db}
OUT_DIR=${2:-/var/lib/node_exporter/textfile_collector}
mkdir -p "$OUT_DIR"
TMP=$(mktemp)

python scripts/db_health.py "$DB" > "$TMP" || true

# parse JSON (jq is convenient; si no está, usar python)
if command -v jq >/dev/null 2>&1; then
  CONN_OK=$(jq -r '.connect.ok' < "$TMP")
  WRITE_OK=$(jq -r '.can_write.ok' < "$TMP")
else
  CONN_OK=$(python -c "import json,sys;print(json.load(sys.stdin)['connect']['ok'])" < "$TMP")
  WRITE_OK=$(python -c "import json,sys;print(json.load(sys.stdin)['can_write']['ok'])" < "$TMP")
fi

cat > "$OUT_DIR/trainsim_db.prom" <<EOF
# HELP trainsim_db_connect_ok DB file can be opened (1=ok,0=fail)
# TYPE trainsim_db_connect_ok gauge
trainsim_db_connect_ok{db="$DB"} $([ "$CONN_OK" = "true" ] && echo 1 || echo 0)
# HELP trainsim_db_can_write DB accepts a write (1=ok,0=fail)
# TYPE trainsim_db_can_write gauge
trainsim_db_can_write{db="$DB"} $([ "$WRITE_OK" = "true" ] && echo 1 || echo 0)
EOF

rm -f "$TMP"
```

Hacer ejecutable y crear cron/systemd timer para ejecutarlo cada 30s/1m. Node Exporter debe tener el textfile collector activado y leer el directorio indicado (`/var/lib/node_exporter/textfile_collector` en ejemplo).

---

## Ejemplo de alertas / reglas Prometheus (concepto)

Regla simple (Prometheus alerting rule):

```yaml
groups:
- name: TrainSimAI.rules
  rules:
  - alert: TrainSimAIDbWriteFailure
    expr: trainsim_db_can_write == 0
    for: 2m
    labels:
      severity: page
    annotations:
      summary: "TrainSimAI DB not accepting writes"
      description: "The SQLite DB at {{ $labels.db }} is not accepting writes for >2m"
```

---

## Notas operativas

- En entornos con I/O lento o alta contención, aumentar `TSC_DB_BUSY_MS` reduce errores por `database is locked`.
- `TSC_DB_SYNCHRONOUS` puede bajarse a `NORMAL` o `OFF` para disminuir latencias en discos lentos, con la consiguiente pérdida de durabilidad ante fallos de energía — evaluar riesgo operativo.
- En Windows, el collector ya usa WAL y `check_same_thread=False` para permitir accesos desde hilos; aun así programar backups y realizar pruebas de restauración periódicas.

---

Si quieres, puedo añadir el wrapper `scripts/db_health_prometheus.sh` y un ejemplo de `systemd` unit/timer para él, y también generar un `docs/operational_examples.md` con capturas de ejemplo. ¿Lo añado ahora?
