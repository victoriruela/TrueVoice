# Git Workflow

Todas las operaciones git en este proyecto siguen las convenciones documentadas aquí.
**Agentes y desarrolladores deben leer este archivo antes de cualquier operación git.**

## Formato del Mensaje de Commit

```
tipo(alcance): descripción
```

### Tipos permitidos

| Tipo | Cuándo usarlo |
|------|---------------|
| `feat` | Nueva funcionalidad |
| `fix` | Corrección de bug |
| `docs` | Documentación únicamente |
| `style` | Formato, sin cambio de código |
| `refactor` | Cambio de código que no corrige un bug ni añade funcionalidad |
| `perf` | Mejora de rendimiento |
| `test` | Añadir o actualizar tests |
| `build` | Sistema de build o dependencias externas |
| `ci` | Configuración CI/CD |
| `chore` | Mantenimiento, sin cambio de código de producción |
| `revert` | Revertir un commit anterior |
| `release` | Release de versión |

### Reglas

- La **cabecera** (primera línea completa) tiene un máximo de **100 caracteres**
- El **alcance** es opcional pero recomendado (p.ej. `feat(api): add voice clone endpoint`)

### Ejemplos

```
feat(api): add progress tracking for audio generation
fix(frontend): fix config not persisting ollama url
docs: update AGENTS.md with docker volume details
feat(parser): add lap 0 formation events support
fix(voices): handle absolute paths with spaces
build: rebuild Docker images with torch 2.2
chore: regenerate docker-compose.override.yml
release: v1.2.0
```

## Branching

| Rama | Propósito |
|------|-----------|
| `main` | Código estable y desplegado en producción |
| `develop` | Integración de features antes del siguiente release |
| `feat/<nombre>` | Nueva funcionalidad (se mergea a `develop`) |
| `fix/<nombre>` | Corrección de bug (se mergea a `develop` o directamente a `main` si es hotfix urgente) |

## Semantic Versioning

| Bump | Cuándo |
|------|--------|
| `PATCH` | Bugfixes sin cambios de API ni comportamiento visible |
| `MINOR` | Nueva funcionalidad backward-compatible |
| `MAJOR` | Cambios de API o arquitectura que rompen compatibilidad |

Tags de release en `main`: `vX.Y.Z` (ej. `v1.2.0`)
Tags de Release Candidate en `develop`: `vX.Y.Z-rc.N` (ej. `v1.2.0-rc.1`)

## Procedimiento de Release

**Nunca desplegar desde un árbol de trabajo sucio o un commit sin tag.**

1. Mergear la(s) rama(s) de feature en `develop`.
2. Validar localmente: `docker compose up --build` y probar en `http://localhost:8501`.
3. Taggear RC: `git tag v1.2.0-rc.1 && git push origin v1.2.0-rc.1`.
4. **GATE OBLIGATORIO**: el agente debe esperar confirmación explícita del propietario humano
   antes de continuar. Proporcionar al usuario las URLs locales para validar:
   - Frontend: `http://localhost:8501`
   - API Health: `http://localhost:8000/`
   - API Docs: `http://localhost:8000/docs`
5. Solo tras aprobación explícita: mergear `develop` → `main`.
6. Taggear release final: `git tag v1.2.0 && git push origin v1.2.0`.
7. Crear el artefacto de despliegue y publicar GitHub Release.

**Política obligatoria**: nunca continuar automáticamente del RC al release final sin confirmación del usuario.

## Linting

TrueVoice no tiene linting automatizado configurado. Recomendaciones:

```bash
# Instalar ruff
pip install ruff

# Verificar calidad del código Python
ruff check api_server.py frontend.py inference_wrapper.py race_parser.py patches.py

# Auto-corregir problemas seguros
ruff check --fix api_server.py frontend.py inference_wrapper.py race_parser.py patches.py
```

Si se añade ruff al proyecto, crear `pyproject.toml` con la configuración y añadir la comprobación
al flujo de pre-commit (husky + commitlint, al igual que rFactor2 Engineer).

## Bypassing Hooks

Si el proyecto llega a tener hooks de pre-commit, **nunca** usar `--no-verify` durante el desarrollo
normal. Si un hook falla:

1. Corregir el problema (error de lint, test fallido, mensaje de commit incorrecto)
2. Volver a hacer staging de los cambios y reintentar el commit

Para casos excepcionales (hotfix de emergencia), documentar la justificación en el cuerpo del mensaje
de commit.
