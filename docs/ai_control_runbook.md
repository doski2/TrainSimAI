# AI Control Runbook for TrainSimAI

Esta guía documenta el estado actual, los riesgos, y los procedimientos operativos para el control del tren por parte de una IA en el proyecto TrainSimAI. Está pensada para operadores, desarrolladores y revisores de seguridad.

## 1. Propósito
Proveer un resumen de cómo la IA puede emitir comandos al tren, qué garantías mínimas de seguridad deben existir, y cómo operar/activar/desactivar el modo de control por IA de forma segura.

## 2. Componentes relevantes
- `ingestion/rd_client.py`: cliente RailDriver. Punto donde se envían comandos `set_*` (throttle, brake, etc.).
- `profiles/controls.py`: mapeo de nombres canónicos y aliases de controles.
- `scripts/db_health_prometheus.py`: generador de métricas Prometheus para observabilidad.
- `data/control_status.json`: archivo usado para estado y takeover manual (legacy/convención; crear si no existe).

> Nota: revisar que `ingestion/rd_client.py` sea el único componente que envía comandos al hardware y que todas las rutas de comandos pasen por una capa de validación.

## 3. Modos operativos propuestos
- `manual` — operador humano controla todo.
- `ai_assist` — IA sugiere comandos; operador valida/acepta.
- `ai_autonomous` — IA en control directo; solo para escenarios con validaciones previas y registro de auditoría.

El modo actual por defecto es `manual`. Antes de permitir `ai_autonomous` debe existir autorización explícita de operador y pruebas de seguridad pasadas.

## 4. Invariantes de seguridad que siempre deben cumplirse
1. No enviar valores fuera de límites físicos (ej. `brake` entre 0..1, `throttle` entre -1..1) — se deben aplicar `clamp()` por defecto.
2. Tasa máxima de comandos por controlador (ej. 5 por segundo) para evitar ráfagas/overload.
3. Timeout/ACK: cada comando espera un ACK no-bloqueante; si no llega en `ack_timeout` reintentar hasta `max_retries`. Tras `max_retries` disparar `emergency_stop()`.
4. Emergency stop es idempotente, de máxima prioridad, y debe escribirse en `data/control_status.json` con timestamp y causa.
5. El operador puede forzar `manual` mediante un takeover manual que se persiste en `data/control_status.json`.

## 5. Procedimientos operativos
### 5.1 Activar `ai_autonomous`
1. Ejecutar batería de tests de seguridad: unit tests, scenario tests (latency, missing ack, sensor faults).
2. Verificar que las métricas Prometheus muestran `rd_errors_total == 0` y `rd_missing_ack_total == 0` en las últimas N horas.
3. El operador ejecuta: `python scripts/set_mode.py --mode ai_autonomous --confirm` (script propuesto) y documenta la causa.
4. Supervisar durante 30 minutos en `ai_autonomous` con un operador atento para confirmar comportamiento normal.

### 5.2 Emergency stop manual
- Operador: ejecutar `python scripts/force_emergency_stop.py` o escribir `{"mode": "manual", "takeover": true, "reason": "EMERGENCY"}` en `data/control_status.json`.
- Sistema: RDClient detecta la señal y llama a `emergency_stop()` que aplica freno a máxima potencia y persiste evento.

## 6. Desarrollo y pruebas recomendadas
- Implementar wrappers de seguridad en `RDClient`:
  - `clamp_command(control, value)` (por perfil/vehículo)
  - `rate_limiter` por control
  - `ack_tracker` con timestamps y reintentos
  - `watchdog` que detenga IA y active E-STOP si se exceden reintentos
- Tests a añadir:
  - Unit: `test_clamp_limits`, `test_rate_limiter`, `test_ack_tracker`.
  - Integration: mock RailDriver con escenarios de pérdida de paquetes y latencia.
  - E2E (simulado): escenarios de respuesta del tren en gradiente/pendientes.

## 7. Observabilidad y alertas
- Métricas mínimas (Prometheus): `rd_commands_total`, `rd_errors_total`, `rd_missing_ack_total`, `rd_emergencystops_total`, `rd_command_rate`.
- Alertas sugeridas:
  - Missing ACKs > 5 en 1 minute -> alert on-call
  - Emergency stops > 0 -> pager

## Thresholds y reglas recomendadas

Se proponen las siguientes reglas iniciales (implementadas en `monitoring/alerts.yml`):

- `TrainsimEmergencyStop`: `trainsim_rd_emergencystops_total > 0` durante 1m -> pager
- `TrainsimHighRetryRate`: `increase(trainsim_rd_retries_total[5m]) > 10` -> warn
- `TrainsimMissingAcks`: si hay sets pero no acks en 5m -> warn

El repositorio incluye un panel Grafana de ejemplo en `monitoring/grafana_simple.json`.

### Habilitar HTTP exporter de Prometheus

  `ingestion/rd_client.py` incluye soporte opt-in para arrancar un endpoint HTTP que expone las métricas de `prometheus_client`.

  Para habilitarlo en entorno local o en despliegue, define la variable de entorno `TSC_PROMETHEUS_PORT` con el puerto donde quieres que escuche (ej. `9188`). Ejemplo en PowerShell:

  ```powershell
  $env:TSC_PROMETHEUS_PORT = "9188";
  python -m your_service_entrypoint
  ```

  El exporter no fallará si `prometheus_client` no está instalado; simplemente no expondrá métricas. Si el exporter arranca, `ingestion.rd_client` registrará un `info` con el puerto.
  - Command rate > X -> alert

## 8. Roles y permisos
- Solo operadores con rol `controller` pueden activar `ai_autonomous`.
- Los desarrolladores deben abrir PR y pasar CI con tests de seguridad para cambios en `ingestion/rd_client.py`.

## 9. Checklist previo a despliegue de IA en real
- [ ] Tests unitarios e integración completados y en CI
- [ ] Simulaciones de stress y escenarios críticas pasadas
- [ ] Runbook aprobado por responsable operativo
- [ ] Monitorización y alertas configuradas
- [ ] Procedimiento de rollback y takeover manual probado

## 10. Archivos relacionados y comandos útiles
- `python -m pytest -q -o addopts=` — ejecutar suite completa de tests
- `ruff check . --fix` + `flake8 .` — linters
- `python scripts/db_health_prometheus.py --out /path/to/artifacts/prom` — generar métricas de health

---

Si quieres, puedo:
- (A) Crear los scripts `scripts/set_mode.py` y `scripts/force_emergency_stop.py` con la lógica mínima para actualizar `data/control_status.json`.
- (B) Implementar `clamp_command` + rate limiter + ack-tracker + watchdog en `ingestion/rd_client.py` y añadir pruebas unitarias.
- (C) Añadir métricas Prometheus en RDShim y pruebas para los contadores.

Dime qué prefieres y procedo con la implementación correspondiente.
