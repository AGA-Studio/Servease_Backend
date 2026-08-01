# Servease Backend — Project Context

## Active Branch
- `feature/erik`

## Stack
- Django 6.0.7 + Django REST Framework 3.17.1
- Channels 4.3.2 + Daphne 4.2.3 / Uvicorn 0.49.0
- PostgreSQL (psycopg2-binary) via Supabase
- JWT auth (PyJWT), Supabase for auth layer
- Gunicorn 26.0.0 (prod — needs uvicorn for ASGI)

## Apps
| App | Status | Endpoints |
|-----|--------|-----------|
| usuarios | Complete | Auth, profiles, CRUD |
| servicios | Complete | Services CRUD, search, filters |
| mensajeria | Complete | Conversations + Messages REST + WebSocket |
| transacciones | Skeleton | No endpoints yet |
| calificaciones | Skeleton | No endpoints yet |

## Tests
- 74 tests passing (63 REST + 11 WebSocket)
- Run: `DJANGO_SETTINGS_MODULE=Servease_Backend.settings python -m django test --keepdb`

## Messaging API
- Conversations: list/create/get/archive
- Messages: list/create/get/edit/delete
- Mark as read: PATCH /api/mensajeria/conversaciones/:id/leer/
- WebSocket: ws://localhost:8000/ws/mensajeria/:conversationId/?token=:token
- Auth: JWT token in query param + JWTAuthMiddleware

## Key Config
- CHANNEL_LAYERS: InMemoryChannelLayer (dev)
- ASGI path: Servease_Backend.asgi.application
- CORS: django-cors-headers configured
