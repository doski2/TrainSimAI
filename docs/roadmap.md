# Hoja de ruta (v1, editable)

## P0 – Boot (2–3 días)
- Instalar RailDriver + wrapper Python.
- Script lectura continua → `runs/*.csv` + dashboard básico (velocidad y límite siguiente manual).

## P1 – Telemetría HUD/LUA (1–2 semanas)
- PoC LUA in-game para `GetNextSpeedLimit` y `GetSpeed` (si viable por escenario).
- Fallback: estimador de límite por señales/blueprints si no hay acceso directo.

## P2 – Modelo de frenado (1–2 semanas)
- Integrar `braking_curves.py` con ERA v5.1 (export CSV desde .xlsm).
- Validar `base/deg` por consist y gradiente.

## P3 – Controlador
- Lazo feed-forward + PID (target en función de distancia a próximo límite y tiempos de parada).
- Añadir márgenes de confort y anticipo (suavizado + seguridad).

## P4 – Señalización y estaciones
- Lectura de estados (si es posible) y planificador de paradas.

## P5 – Endurecer & empaquetar
- Perfiles por tren/ruta, tolerancias, grabación completa, README + vídeos.

## Checklist inicial (tick-box)
- [ ] RailDriver instalado y calibrado
- [ ] `py-raildriver` lee velocidad real
- [ ] `runs/*.csv` se genera
- [ ] Plantilla `docs/diario.md` creada y en uso
- [ ] `research/refs.md` con enlaces y notas
- [ ] Roadmap `docs/roadmap.md` actualizado
