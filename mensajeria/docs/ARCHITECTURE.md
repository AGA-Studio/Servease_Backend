# mensajeria — Arquitectura y Decisiones

## Modelos
- **Conversacion**: 1 cliente + 1 proveedor. `archivada` (soft-delete).
- **Mensaje**: `emisor` (FK Usuario), `contenido`, `estado_entrega`, `editado`, `respuesta_a` (thread).
- **Bloqueo**: Usuario A bloquea a B → no pueden crear conversación ni enviar mensajes.

## Triggers PostgreSQL (críticos)
| Trigger | Tabla | Acción |
|---|---|---|
| `validate_mensaje_insert` | `mensajeria_mensaje` | `RAISE MSG_IN_ARCHIVED` si conversación archivada; `RAISE MSG_SENDER_BLOCKED` si emisor bloqueado |
| `update_conversacion_preview` | `mensajeria_mensaje` | Actualiza `preview`, `unread_count`, `ultima_actividad` en insert/update/delete |

> **Regla**: Nunca insertar `Mensaje` directo en shell/admin sin pasar por `ChatConsumer._save_message` o `MensajeViewSet.create`.

## WebSocket (Channels)
- **Ruta**: `ws/mensajeria/<conversacion_id>/?token=<jwt>`
- **Consumer**: `ChatConsumer` (`consumers.py`)
- **Acciones**: `new_message`, `typing_start`, `typing_stop`, `read_receipt`
- **Rate limit**: `WS_RATE_LIMIT = 10 msg/s` (configurable via `patch.object` en tests)

## REST Endpoints
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/mensajeria/conversaciones/` | Listar (paginado) |
| POST | `/api/mensajeria/conversaciones/` | Crear con `proveedor_id` |
| GET | `/api/mensajeria/conversaciones/{id}/` | Detalle (solo participantes) |
| DELETE | `/api/mensajeria/conversaciones/{id}/` | Archivar (soft) |
| GET | `/api/mensajeria/conversaciones/{id}/mensajes/` | Listar mensajes |
| POST | `/api/mensajeria/conversaciones/{id}/mensajes/` | Enviar mensaje |
| PATCH | `/api/mensajeria/conversaciones/{id}/leido/` | Marcar como leído |
| PATCH | `/api/mensajeria/conversaciones/{id}/mensajes/{mid}/` | Editar (solo emisor) |
| DELETE | `/api/mensajeria/conversaciones/{id}/mensajes/{mid}/` | Soft-delete |
| POST | `/api/mensajeria/bloquear/` | Bloquear usuario |
| GET | `/api/mensajeria/bloquear/` | Listar bloqueos |
| DELETE | `/api/mensajeria/bloquear/{id}/` | Desbloquear |

## Tests
```bash
just test mensajeria
# Incluye: unit (views, serializers), WS (consumers), read-receipts, rate-limit
```
