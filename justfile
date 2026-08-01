# Servease Backend — dev commands
# Dependencies: uv (triggers install), PostgreSQL running

# ── Python / Local ──

# Install/update deps
install:
	pip install -r requirements.txt

# Run DB migrations
migrate:
	python manage.py migrate

# Seed test data (idempotent)
seed *FLAGS:
	python manage.py seed {{FLAGS}}

# Full local dev setup: migrate + seed
setup:
	python manage.py migrate
	python manage.py seed

# Run dev server (Django runserver - no WebSocket)
runserver:
	python manage.py runserver

# Run dev server with ASGI + Channels (WebSocket support)
rundev:
	uvicorn Servease_Backend.asgi:application --reload --host 0.0.0.0 --port 8000

# Django check / type-check
check:
	python manage.py check --deploy
	python -m django check

# Run tests
test *ARGS:
	python manage.py test {{ARGS}}

# Make migrations (scaffold)
makemigrations:
	python manage.py makemigrations

# Shell Plus (django-extensions if installed)
shell:
	python manage.py shell

# ── Docker / Compose ──

# Start infra services (postgres + redis) in background
infra:
	docker compose up -d postgres redis

# Start Supabase local stack
supabase:
	docker compose up -d supabase-db supabase-kong supabase-auth supabase-rest supabase-realtime supabase-storage supabase-meta supabase-studio

# Start full stack (infra + supabase + backend) in background
up:
	docker compose up -d

# Stop all compose services
down:
	docker compose down

# Rebuild backend image and restart
rebuild:
	docker compose build backend
	docker compose up -d

# Tail logs from compose services
logs *SERVICE:
	docker compose logs -f {{ SERVICE }}

# Run manage.py commands inside the running backend container
dc *ARGS:
	docker compose exec backend python manage.py {{ ARGS }}

# ── One-command bootstrap ──

# Full dev bootstrap: venv + deps + infra + supabase + migrate + seed
bootstrap:
	bash scripts/bootstrap.sh

# Quick dev start (re-uses existing infra)
dev:
	bash scripts/start-dev.sh

# Seed data (idempotent)
seed-data:
	bash scripts/seed.sh

# Production certification test
cert:
	bash scripts/cert.sh

# ── OpenAPI / Docs ──

# Generate OpenAPI schema to file
schema:
	python manage.py spectacular --file schema.yml

# Validate schema
schema-check:
	python manage.py spectacular --validate
