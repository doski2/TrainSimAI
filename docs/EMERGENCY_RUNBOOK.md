# EMERGENCY RUNBOOK

Propósito
--------
Pasos rápidos y reproducibles para diagnosticar y mitigar incidentes relacionados con el subsistema de control y la integración con RailDriver (RD).

Prioridad: Alta — aplicar cuando el sistema entra en modo emergency, deja de aplicar comandos o los ACKs fallan repetidamente.

Variables de entorno importantes
--------------------------------
- `TSC_PROMETHEUS_PORT` — si está definido, el proceso expondrá métricas Prometheus.
- `TSC_RD_EMERGENCY_THRESHOLD` — valor límite configurado para escalado a emergencia (si aplica).

Pasos de diagnóstico rápido
---------------------------
1. Recolectar artefactos desde el host (usa `scripts/diagnose_emergency.ps1`):
   ```powershell
   & .\scripts\diagnose_emergency.ps1 -OutDir .\artifacts\incident-$(Get-Date -Format yyyyMMdd-HHmmss)
   ```
2. Revisar los artefactos clave:
   - `data/control_status.json` — estado de los controles antes del fallo
   - `data/rd_ack.json` — historial de ACKs
   - `data/rd_send.log` — logs de envío a RD
   - `logs/*.log` — logs del servicio (si existen)
3. Validar si existen ACKs para los controladores afectados y timestamps para detectar latencia.
4. Si hay comandos repetidos sin ACK, considera activar `emergency_stop()` y cortar salida a actuadores.

Pasos de mitigación (temporal)
------------------------------
- Modo manual: detener el control automático y trabajar en modo manual (si tu operación lo permite).
- Si la train está en riesgo, activar freno de emergencia físicamente y seguir procedimientos de seguridad local.

Cómo reportar el incidente
--------------------------
1. Adjunta el `.zip` con artefactos recogidos.
2. Incluye la salida del comando `git rev-parse --short HEAD` y una breve descripción de la reproducción.

Contacto y seguimiento
----------------------
- Equipo: `@tsc-ops` (channel / correo según tu proceso interno)

Notas finales
------------
- Este runbook es un punto de partida. Actualiza con pasos específicos de tu operación si la infraestructura cambia.
