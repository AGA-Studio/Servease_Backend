# mensajeria — Arquitectura y Decisiones

## Modelos
- **Conversacion**: 1 cliente + 1 proveedor. `estado` es FK a `servicios.Estado`
  (`ACTIVA=9` / `ARCHIVADA=10`). `servicio` nullable (chat directo sin servicio).
  Soft-delete vía `estado=ARCHIVADA`.
- **Mensaje**: `emisor` (FK Usuario), `contenido`, `estado_entrega`
  (`enviado`/`recibido`/`leido`), `editado`, `reply_to` (thread), `archivo`.

## Triggers PostgreSQL (críticos)
| Trigger | Tabla | Acción |
|---|---|---|
| `validate_mensaje_insert` | `mensaje` | `RAISE MSG_IN_ARCHIVED` si la conversación está archivada (`estado_id=10`); auto-default `estado_entrega='enviado'`, `tipo_mensaje='texto'` |
| `maintain_conversacion_meta` | `mensaje` | Actualiza `unread_count`, `ultimo_mensaje_preview`, `ultimo_mensaje_fecha` |
| `mark_mensaje_editado` | `mensaje` | `editado=TRUE` al cambiar contenido |
| `decrement_unread_on_soft_delete` | `mensaje` | Decrementa `unread_count` al soft-deletear un mensaje no leído |

> **Regla**: Nunca insertar `Mensaje` directo en shell/admin — siempre por el
> endpoint REST (los triggers mantienen la metadata de la conversación).

## Realtime (Supabase Realtime — reemplaza Django Channels + Redis)
- **Publicación**: `mensajeria/realtime.py::publish_event(conversacion_id, event, payload)`.
  Fire-and-forget en hilo daemon; best-effort (si Realtime falla, el REST sigue
  funcionando). Canal: `conversacion-<id>`.
- **Eventos**: `new_message`, `typing_start`, `typing_stop`, `read_receipt`.
- **Suscripción**: el frontend se suscribe al canal `conversacion-<id>` con el
  service key/anon key de Supabase; no hay websockets propios.
- **Cliente**: `supabase.create_async_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)`
  → `channel(channel_name)` → `subscribe()` → `send_broadcast(event, data)` → `remove_channel`.

## REST Endpoints
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/mensajeria/conversaciones/` | Listar (paginado, solo activas) |
| POST | `/api/mensajeria/conversaciones/` | Crear con `proveedor_id` |
| GET | `/api/mensajeria/conversaciones/{id}/` | Detalle (solo participantes) |
| DELETE | `/api/mensajeria/conversaciones/{id}/` | Archivar (`estado_id=ARCHIVADA`) |
| POST | `/api/mensajeria/conversaciones/{id}/typing/` | Publicar `typing_start`/`typing_stop` |
| GET | `/api/mensajeria/conversaciones/{id}/mensajes/` | Listar mensajes (marca pendientes del otro como `recibido`) |
| POST | `/api/mensajeria/conversaciones/{id}/mensajes/` | Enviar mensaje (publica `new_message`) |
| PATCH | `/api/mensajeria/conversaciones/{id}/leido/` | Marcar como leído (publica `read_receipt`) |
| PATCH | `/api/mensajeria/conversaciones/{id}/mensajes/{mid}/` | Editar (solo emisor) |
| DELETE | `/api/mensajeria/conversaciones/{id}/mensajes/{mid}/` | Soft-delete |
| GET | `/api/mensajeria/mensajes/{mid}/archivo/` | Descargar adjunto |

## Tests
```bash
python manage.py test mensajeria
# REST + publish_event (mockeado en mensajeria.views.publish_event); sin WS.
# test_realtime.py cubre el flujo real de Supabase Realtime (clientes fake).
```
