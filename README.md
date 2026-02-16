# ATHOS

Current project state is a proof-of-concept stack:
- Frontend: React + Vite
- Backend: FastAPI
- Database: Postgres 16
- Orchestration: Docker Compose

## Prerequisites

Required:
- Docker Desktop (or Docker Engine + Compose plugin)

Recommended:
- Git

Not required for the standard startup flow (`docker compose up`):
- Node.js / npm (frontend runs in container)
- Python / pip / virtualenv (backend runs in container)

## Getting Started

1. Clone and enter the repo.
```bash
git clone <repo-url>
cd ATHOS
```

2. Confirm `.env` exists in repo root.
```bash
ls -la .env
```

If `.env` does not exist, create it using this template (replace placeholder secret values):
```bash
cat > .env <<'EOF'
# Postgres
POSTGRES_USER=<db_user>
POSTGRES_PASSWORD=<db_password>
POSTGRES_DB=fitness

# App
JWT_SECRET=<jwt_secret>
DATABASE_URL=postgresql+psycopg://<db_user>:<db_password>@db:5432/fitness
VITE_API_BASE_URL=http://localhost:8000
EOF
```

3. Build and start all services.
```bash
docker compose up --build
```

4. Open the apps:
- Frontend: http://localhost:5173
- Backend health: http://localhost:8000/health
- Postgres: localhost:5432

## Verify Services

In another terminal:

Check container status:
```bash
docker compose ps
```

Check Postgres readiness:
```bash
docker compose exec db pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

Run a simple DB query:
```bash
docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1;"
```

## Stop the Stack

Stop containers:
```bash
docker compose down
```

Stop and remove DB volume (destructive for local data):
```bash
docker compose down -v
```
