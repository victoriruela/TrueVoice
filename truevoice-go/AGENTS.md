# AGENTS.md - truevoice-go (Backend Go)

## Estructura

```text
truevoice-go/
+- cmd/truevoice/main.go        # Entry point
+- go.mod                        # Go module (chi/v5)
+- internal/
   +- server/
   |  +- server.go               # Router (chi), Server struct, buildRouter()
   |  +- handlers.go             # Config, Ollama, Browse handlers
   |  +- static.go               # Embed webdist/ y servir frontend
   |  +- webdist/                # Build de Expo Web (embebido con //go:embed)
   +- generation/
   |  +- generation.go           # TTS manager, progress, subprocess vibevoice_app.py
   |  +- bootstrap.go            # Python runtime bootstrap
   +- race/
   |  +- parser.go               # XML parser rFactor2
   |  +- handlers.go             # Race HTTP handlers (parse, intro, descriptions, sessions, CSV)
   +- voices/
   |  +- voices.go               # Voice file resolution y upload
   +- config/
   |  +- config.go               # Config store (frontend_config.json), thread-safe
   +- contexts/
      +- manager.go              # Context template CRUD, JSON persistence
      +- handlers.go             # Context HTTP handlers (list, state, get, save, load, delete)
```

## Reglas

1. **Compilar siempre despues de cambios:** `go build ./...`
2. **Tests obligatorios:** `go test ./...` y `go test ./internal/server -run TestE2E -v`
3. **webdist/ NO se edita manualmente.** Se genera desde `truevoice-web` con Expo export y se copia.
4. **Nuevos handlers en server.go:** Registrar rutas en `buildRouter()`. Actualizar API Endpoints en AGENTS.md raiz.
5. **Config store** es thread-safe (`sync.RWMutex`). Usar `cfg.Get()` / `cfg.GetString()` / `cfg.Patch()`.
6. **Cada modulo de internal/ expone handlers HTTP** que el server registra — no poner logica HTTP en server.go.

## Patron para nuevos modulos

```go
// internal/newmodule/manager.go
type Manager struct {
    cfg *config.Store
    mu  sync.RWMutex
}

func NewManager(cfg *config.Store) *Manager { ... }

// internal/newmodule/handlers.go
func (m *Manager) ListHandler(w http.ResponseWriter, r *http.Request) { ... }
```

Registrar en `server.go`:
```go
import "truevoice/internal/newmodule"
// En Server struct:
newmod *newmodule.Manager
// En constructor:
newmod: newmodule.NewManager(cfg),
// En buildRouter:
r.Get("/newmod", s.newmod.ListHandler)
```

## Dependency Injection

Todos los managers reciben `*config.Store` en el constructor. No usar variables globales.
