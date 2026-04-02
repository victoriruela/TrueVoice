# Asana MCP Constants

| Constante | Valor |
|-----------|-------|
| Client ID | `1213839429134637` |
| MCP endpoint | `https://mcp.asana.com/v2/mcp` |
| Redirect URI | `https://localhost/` |
| Token lifetime | 3600s |
| Token audience | `mcp-service` |
| Protocol version | `2024-11-05` |
| Available tools | 22 |
| Workspace GID | `1213846793386214` |

## Proyecto TrueVoice

| Constante | Valor |
|-----------|-------|
| Nombre del proyecto | `TrueVoice` |
| Project GID | `[PENDIENTE — rellenar tras crear el proyecto en Asana]` |
| Workspace GID | `1213846793386214` |

> **Importante**: Una vez creado el proyecto en Asana, actualizar este archivo y `AGENTS.md`
> con el GID real del proyecto en el mismo commit.

## Secciones del Board

| Sección | GID |
|---------|-----|
| `To Do` | `[PENDIENTE]` |
| `In Progress` | `[PENDIENTE]` |
| `In Review` | `[PENDIENTE]` |
| `Done` | `[PENDIENTE]` |

> Obtener los GIDs reales con `get_project(project_id, include_sections=True)` y actualizar esta tabla.

Ver [`ASANA.md`](ASANA.md) para la documentación completa del plugin y su uso.
