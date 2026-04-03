# Git Workflow

Todas las operaciones git en este proyecto siguen estas convenciones.

## Formato del Mensaje de Commit

```text
tipo(alcance): descripcion
```

Tipos permitidos: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`, `release`.

## Branching

- `main`: codigo estable y desplegado
- `develop`: integracion previa a release
- `feat/<nombre>`: funcionalidades (merge a `develop`)
- `fix/<nombre>`: correcciones (merge a `develop` o `main` si hotfix)

## Semantic Versioning

- `PATCH`: correcciones sin cambios visibles de API
- `MINOR`: funcionalidad nueva compatible
- `MAJOR`: cambios incompatibles de API/arquitectura

Tags:
- Release final en `main`: `vX.Y.Z`
- RC en `develop`: `vX.Y.Z-rc.N`

## Procedimiento de Release

1. Merge de feature branch a `develop`.
2. Validar localmente (`go test ./...` en `truevoice-go` y smoke de endpoints principales).
3. Taggear RC en `develop` (`vX.Y.Z-rc.N`) y push del tag.
4. **GATE OBLIGATORIO**: esperar confirmacion humana explicita para pasar a release final.
5. Tras aprobacion, merge `develop` -> `main`.
6. Tag final `vX.Y.Z` en `main` y push del tag.
7. Publicar release y artefactos.

URLs de validacion sugeridas:
- UI: `http://localhost:8000/app`
- Health: `http://localhost:8000/`

## Validacion Recomendada

```bash
cd truevoice-go
go test ./...
```

Si hubo cambios frontend:

```bash
cd truevoice-web
node .\node_modules\expo\bin\cli export --platform web
```
