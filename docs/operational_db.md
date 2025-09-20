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
# Playbook operativo — TrainSimAI

Este documento provee patrones, ejemplos de alertas y pasos de emergencia para operar TrainSimAI. Está pensado para SREs/operadores que manejan la integración IA + tren (simulado) y la base de datos SQLite utilizada como fuente de verdad.

## Objetivos
- Detectar condiciones inseguras (no-ack de actuador, telemetría obsoleta, DB inaccesible).
- Proveer pasos claros para mitigar, diagnosticar y recuperar.
- Entregar reglas de Prometheus/Grafana de ejemplo para alertas y dashboards.

## Archivos importantes
- `data/control_status.json` — estado persistente del último comando de control y timestamp del último ack.
- `data/rd_ack.json` — ack del actuador (stub) con timestamp cuando aplica un comando.
- `data/run.db` — base de datos principal SQLite con registros de ejecución.
- `artifacts/trainsim_db.prom` — output del script `scripts/db_health_prometheus.py` que Prometheus puede leer (textfile collector).

## Métricas exportadas (por `scripts/db_health_prometheus.py`)
- `trainsim_db_connect_ok{db,instance,mode}` (gauge: 1/0)
- `trainsim_db_can_write{db,instance,mode}` (gauge: 1/0)
- `trainsim_control_last_command_timestamp{instance,mode}` (gauge: unix_ts)
- `trainsim_control_last_ack_timestamp{instance,mode}` (gauge: unix_ts)
- `trainsim_control_last_command_value{instance,mode}` (gauge: 0..1)

Labels:
- `instance`: valor de env `TSC_INSTANCE` o hostname si no está definida.
- `mode`: valor de env `TSC_MODE` (por ejemplo `sim`, `real`, `test`) o `unknown`.

## Alertas de ejemplo (Prometheus rules)

Regla 1 — Ack timed out (posible pérdida de actuador)
```
# Alert if last_ack is older than 10s since last_command
- alert: TrainSim_Actuator_AckTimeout
  expr: |
    (
      trainsim_control_last_command_timestamp - trainsim_control_last_ack_timestamp
    ) > 10
  for: 30s
  labels:
    severity: critical
  annotations:
    summary: "Ack timeout for TrainSim control on {{ $labels.instance }}"
    description: "Last ack older than 10s from last command. Check actuator and communications."
```

Regla 2 — Telemetría obsoleta (control puede estar operando sin datos frescos)
```
- alert: TrainSim_Telem_Stale
  expr: time() - max_over_time(trainsim_telemetry_timestamp[1m]) > 5
  for: 30s
  labels:
    severity: warning
  annotations:
    summary: "Telemetry stale for TrainSim on {{ $labels.instance }}"
    description: "Telemetry age exceeds 5s. Investigate ingestion pipeline."
```

Regla 2b — Telemetría envejecida basada en el exporter (edad de último muestreo)
```
- alert: TrainSim_Telem_Age_High
  expr: trainsim_control_telemetry_age_seconds > 5
  for: 30s
  labels:
    severity: warning
  annotations:
    summary: "Telemetry age high for TrainSim on {{ $labels.instance }}"
    description: "The last telemetry sample is older than 5s according to trainsim_control_telemetry_age_seconds."
```

Regla 3 — DB write failures
```
- alert: TrainSim_DB_Write_Failed
  expr: trainsim_db_can_write == 0
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: "TrainSim DB write failure on {{ $labels.instance }}"
    description: "DB write attempted but failed. Check disk space, locks and DB health."
```

## Pasos de emergencia (Playbook)

Escenario A: `Actuator ack timeout` (alert `TrainSim_Actuator_AckTimeout`)
1. Cambiar a control manual (si aplica): parar la lógica IA en el host que corre `ControlLoop`.
   - Si el proceso corre como systemd: `sudo systemctl stop trainsim-control` (ajustar nombre de servicio).
2. Forzar freno máximo desde el lado del operador (PLC/driver o simulador): ejecutar el comando manual que aplique `brake=1.0`.
3. Revisar `data/rd_ack.json` y `data/control_status.json`:
   - `Get-Content data\\rd_ack.json -Raw`
   - `Get-Content data\\control_status.json -Raw`
4. Si `rd_ack.json` no se actualiza, inspeccionar logs del actuador (`runtime/raildriver_stub.py` o logs del proceso real).
5. Verificar conectividad/disco y locks:
   - `df -h` o `Get-PSDrive`
   - Revisar `sqlite` locks: usar `sqlite3` y `PRAGMA wal_checkpoint;` o `PRAGMA integrity_check;`.
6. Reiniciar actuador o su stub, observar si los acks vuelven.
7. Una vez ack restaurado, reactivar proceso IA y monitorizar métricas durante 5 minutos.

Escenario B: `DB write failures` (alert `TrainSim_DB_Write_Failed`)
1. Ver logs del proceso que escribe en DB (RunStore / collector).
2. Chequear espacio en disco y permisos.
3. Ejecutar `sqlite3 data/run.db 'PRAGMA integrity_check;'
4. Intentar aplicar `PRAGMA wal_checkpoint(TRUNCATE);` y revisar `busy_timeout`.
5. Si persistente, apagar procesos que escriben y recuperar DB desde backup o CSV logs (`data/runs/*.csv`).

## Recomendaciones operativas
- Ejecutar Prometheus node exporter y usar `textfile collector` apuntando al directorio de `artifacts/` donde `scripts/db_health_prometheus.py` deja `trainsim_db.prom`.
- Mantener `TSC_DB_BUSY_MS` configurado razonablemente (p. ej. 5000ms) si hay concurrencia en el acceso a SQLite.
- Para producción real: usar una base de datos cliente/servidor (Postgres) si hay múltiples procesos concurrentes que escriben frecuentemente.

## Comandos útiles (PowerShell)
```
# Revisar control status
Get-Content data\\control_status.json -Raw | ConvertFrom-Json

# Forzar freno máximo (dependiente del setup): ejemplo directo con stub
python -c "from runtime.raildriver_stub import RdStub; RdStub().set_brake(1.0)"

# Ejecutar exporter localmente
python -m scripts.db_health_prometheus data\\run.db --out artifacts\\trainsim_db.prom
```

## Checklist post-incidente
- Documentar root cause en `docs/incidents/` con timestamp y pasos ejecutados.
- Subir `artifacts/trainsim_db.prom` y `artifacts/sqlite_stress.json` a almacenamiento de incidentes.
- Evaluar si subir a Postgres en caso de carga/concurrencia sostenida.

---
Documentado por el equipo de SRE/DevOps — ajusta paths y comandos a tu despliegue real.
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
