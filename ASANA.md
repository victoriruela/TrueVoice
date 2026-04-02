# Asana MCP Integration

La integración con Asana está gestionada por el **plugin `asana-mcp` de Claude Code**.

## Instalación

Descomprimir el plugin en `~/.claude/asana-mcp/`:

```powershell
# Windows (PowerShell)
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.claude\asana-mcp"
Expand-Archive -Path asana-mcp-plugin.zip -DestinationPath "$env:USERPROFILE\.claude\asana-mcp"
```

> El plugin ya está instalado si también usas rFactor2 Engineer — ambos proyectos comparten la
> misma instalación del plugin en `~/.claude/asana-mcp/`.

## Referencia Rápida

```bash
# Verificar estado actual (token, config, IDEs detectados)
python ~/.claude/asana-mcp/scripts/asana_mcp.py status

# Configuración inicial (crea config.json)
python ~/.claude/asana-mcp/scripts/asana_mcp.py setup

# Autenticar (refresh o OAuth2 completo)
python ~/.claude/asana-mcp/scripts/asana_mcp.py auth

# Escribir token en todas las configs de IDE detectadas
python ~/.claude/asana-mcp/scripts/asana_mcp.py update-mcp

# Escribir en IDE(s) específico(s)
python ~/.claude/asana-mcp/scripts/asana_mcp.py update-mcp --target copilot-vscode claude-desktop

# Smoke test de la conexión MCP
python ~/.claude/asana-mcp/scripts/asana_mcp.py test
```

## IDEs Soportados

| Target              | Formato                                             |
|---------------------|-----------------------------------------------------|
| `copilot-jetbrains` | `servers.asana-mcp.requestInit.headers`             |
| `copilot-vscode`    | `servers.asana-mcp` con `type`/`url`/`headers`      |
| `claude-desktop`    | `mcpServers.asana-mcp` con `type`/`url`/`headers`   |
| `claude-cli`        | `mcpServers.asana-mcp` con `type`/`url`/`headers`   |

## Proyecto Canónico de Asana

El proyecto Asana para TrueVoice es **"TrueVoice"**.

> **Nota**: el GID del proyecto debe rellenarse tras su creación en Asana. Actualizar
> `AGENTS.md` y `ASANA_CONSTANTS.md` en ese mismo commit.

### Board Layout

El proyecto usa **Board layout** con cuatro secciones fijas (crear si no existen):

| Sección | Significado |
|---------|-------------|
| `To Do` | Tarea creada, no iniciada |
| `In Progress` | Subagente trabajando activamente |
| `In Review` | Subagente hizo commit; supervisor revisando |
| `Done` | Mergeada y verificada |

Al crear tareas, siempre proporcionar `section_id` apuntando al GID de la sección `To Do`.
Obtener los GIDs de sección con `get_project(project_id, include_sections=True)`.

## Protocolo de Fallo MCP — OBLIGATORIO

Las herramientas `mcp_asana-mcp_*` se autentican mediante un token almacenado en el archivo de
configuración del IDE. El token **expira cada hora**. El IDE lo **cachea al arrancar** y no lo
recarga en mitad de sesión.

Cuando cualquier llamada `mcp_asana-mcp_*` falle con `invalid_token`:

```
Paso 1 — Refrescar y re-inyectar el token (ejecutar en terminal):
    python "$env:USERPROFILE\.claude\asana-mcp\scripts\asana_mcp.py" auth
    python "$env:USERPROFILE\.claude\asana-mcp\scripts\asana_mcp.py" update-mcp

Paso 2 — Reintentar la herramienta MCP inmediatamente (el token en el
    archivo de config ya es válido; a veces el IDE lo recoge sin reiniciar).

Paso 3 — Si la herramienta sigue fallando:
    ► PARAR. Decirle al usuario:
      "El token de Asana MCP ha sido refrescado y escrito en la config del
       IDE, pero el IDE tiene cacheado el token anterior. Por favor reinicia
       el IDE y luego dime que continúe."
    ► Esperar confirmación del usuario antes de hacer nada más.

NUNCA crear un script Python alternativo que llame a la API de Asana o al
endpoint MCP directamente. NUNCA saltarse silenciosamente las herramientas MCP.
```

## Documentación Completa

Ver los archivos del plugin:
- `~/.claude/asana-mcp/skills/asana-mcp/SKILL.md`
- `~/.claude/asana-mcp/skills/asana-mcp/references/mcp-protocol.md`

Ver también [`ASANA_CONSTANTS.md`](ASANA_CONSTANTS.md) para los valores de configuración del cliente MCP.
