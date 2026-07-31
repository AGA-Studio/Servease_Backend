# Servease Backend

Plataforma de servicios profesionales con mensajería en tiempo real, autenticación vía Supabase, y PostgreSQL.

## Stack

- **Python 3.14** / **Django 6.0** + **DRF** + **Channels**
- **PostgreSQL 17** (principal)
- **Redis 7** (channel layer / WebSocket)
- **Supabase Auth** (JWT)
- **Uvicorn** (ASGI server)

## Quick Start (desarrollo local)

**Prerrequisitos:** Docker, Python 3.13+, Supabase CLI (`brew install supabase/tap/supabase`)

```bash
# Opción 1 — bootstrap completo (recomendado)
bash scripts/bootstrap.sh

# Opción 2 — paso a paso
cp .env.example .env             # 1. Variables de entorno
python -m venv venv && source venv/bin/activate  # 2. Virtual env
pip install -r requirements.txt  # 3. Dependencias

docker compose up -d postgres redis  # 4. Postgres + Redis
supabase start                       # 5. Supabase local

python manage.py migrate         # 6. Migraciones
python manage.py seed             # 7. Datos de prueba
just rundev                       # 8. Servidor con hot reload
```

### Con `just` (si lo tienes instalado)

```bash
just bootstrap   # Todo en uno
just dev         # Iniciar servicios + servidor
just infra       # Solo postgres + redis
just up          # docker compose up -d (todo)
just down        # docker compose down
```

## Servicios

| Servicio | Puerto | URL |
|---|---|---|
| Backend (uvicorn) | `8000` | `http://localhost:8000` |
| Healthcheck | — | `http://localhost:8000/health/` |
| PostgreSQL | `5432` | `postgresql://servease_dev:servease_dev@localhost:5432/servease_dev` |
| Redis | `6379` | `redis://localhost:6379/0` |
| Supabase Auth | `54321` | `http://localhost:54321/auth/v1` |
| Supabase Studio | `54323` | `http://localhost:54323` |

## Endpoints principales

```
GET    /health/                          — Healthcheck (DB + Redis + Supabase)
POST   /api/usuarios/auth/registro/      — Registro
POST   /api/usuarios/auth/inicio/        — Login
GET    /api/mensajeria/conversaciones/   — Listar conversaciones
POST   /api/mensajeria/conversaciones/   — Crear conversación
DELETE /api/mensajeria/conversaciones/1/ — Archivar
POST   /api/mensajeria/conversaciones/1/mensajes/  — Enviar mensaje
GET    /api/mensajeria/conversaciones/1/mensajes/   — Listar mensajes
POST   /api/mensajeria/bloquear/         — Bloquear usuario
WS     /ws/mensajeria/1/                 — WebSocket en tiempo real
```

## Tests

```bash
just test              # Todos los tests unitarios
just test mensajeria   # Tests de mensajería
just cert              # Certificación producción (requiere servidor corriendo)
```

## Producción

En producción solo se necesita cambiar las variables de entorno. No hay diferencias en el código:

- `SUPABASE_URL` → apunta a Supabase cloud
- `SUPABASE_JWKS_URL` → apunta a Supabase cloud
- `SUPABASE_ANON_KEY` → key de producción
- `REDIS_URL` → Redis administrado (Upstash, Redis Cloud, etc.)
- `DB_HOST` → base de datos administrada (Railway, Render, Neon, etc.)
- `DEBUG=False`

El **Procfile** ya está configurado para Railway/Render/Fly:
```procfile
web: python manage.py collectstatic --noinput && python manage.py migrate && uvicorn Servease_Backend.asgi:application --host 0.0.0.0 --port $PORT
```

## Variables de entorno

Ver `.env.example` — todas las variables tienen valores por defecto para desarrollo local excepto `SECRET_KEY` y credenciales de Supabase cloud.
