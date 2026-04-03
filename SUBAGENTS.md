# SUBAGENTS.md - Flujo operativo Asana + Subagentes

Este archivo define como paralelizar trabajo en TrueVoice usando Asana como sistema de verdad.

## Regla principal

Cada bloque de trabajo debe existir como tarea en Asana dentro del proyecto **TrueVoice** (GID `1213903547619538`) antes de ejecutar cambios.

## Secciones del board

- `Pending`: tarea creada, sin ejecucion.
- `In Progress`: tarea activa, asignada al subagente o al agente principal.
- `In Hold`: bloqueada por dependencia externa o decision pendiente.
- `Done`: implementada, validada y mergeada.

## Protocolo de ejecucion

1. Crear tarea en `Pending` con prefijo de dominio (`[GO-*]`, `[EXPO]`, `[PACKAGING]`, `[DOCS]`).
2. Mover a `In Progress` al iniciar trabajo.
3. Ejecutar exploracion con subagentes en paralelo para reducir tiempo de contexto.
4. Consolidar resultados en una sola implementacion coherente.
5. Al terminar validacion (build/lint/smoke), mover a `Done`.
6. Si hay bloqueo real, mover a `In Hold` con comentario de causa y siguiente accion.

## Paralelizacion recomendada

- Subagente A: contratos API (Go handlers, rutas, payloads).
- Subagente B: frontend Expo (stores, cliente HTTP, pantallas).
- Subagente C: sidecar Python (bootstrap, dependencias, proceso de inferencia).
- Agente principal: integra cambios, ejecuta validaciones y cierra tareas en Asana.

## Criterios de cierre de tarea

- Codigo compilable para el area afectada.
- Endpoints o UI probados en flujo minimo.
- Sin regresiones obvias en rutas existentes.
- Documentacion obligatoria actualizada (AGENTS.md y constantes relevantes cuando aplique).

## Convenciones de nombres de tarea

- `[GO-CORE] ...`
- `[GO-AUDIO] ...`
- `[GO-RACE] ...`
- `[GO-ENV] ...`
- `[EXPO] ...`
- `[PACKAGING] ...`
- `[DOCS] ...`

## Nota de control

No ejecutar trabajo fuera de Asana. Si no existe tarea, se crea primero.