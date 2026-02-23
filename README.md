# ATHOS

ATHOS is currently in backend-first proof-of-concept mode, with frontend wiring ready to begin.

## Stack
- Frontend: React + Vite + TypeScript + React Router
- Backend: FastAPI
- ORM: SQLAlchemy 2.0
- Migrations: Alembic
- Auth: JWT bearer tokens
- Database: Postgres 16
- Orchestration: Docker Compose
- Tests:
  - Backend: Python `unittest` integration suites (`./backend_tests`)
  - Frontend: Vitest (client/token store coverage)

## Current State

Implemented and validated:
- Auth: `POST /v1/auth/signup`, `POST /v1/auth/login`, `GET /v1/auth/me`
- Workouts write: `POST /v1/workouts`
- Workouts read: `GET /v1/workouts`, `GET /v1/workouts/{id}`
- Dashboard read: `GET /v1/dashboard/day`
- User-scoped data access and idempotent create (`client_uuid`)
- Alembic migrations for users + workout domain tables
- Vite/React Router + protected routes (`/workout`, `/dashboard`)
- API client with auth support + `X-Client-Timezone` header
- Login flow with error handling and surfaced `X-Request-ID`
- Workout entry toggle form (strength/cardio)
- Dashboard JSON dump (date-scoped)
- Request observability:
  - `X-Request-ID` on responses
  - structured request logs (`athos.request`)
  - domain event logs (auth/workouts/dashboard)
- CORS enabled for Vite local dev (`http://localhost:5173`)
- CORS exposes `X-Request-ID` (`Access-Control-Expose-Headers` regression test included)
- README runbook refreshed (startup, migrations, logs, smoke path)

## What’s Next
- Signup UI page (backend endpoint exists)
- Cardio contract alignment (currently mapping extra cardio fields into `notes`)
- Strength payload validation UX (required reps/weight and numeric constraints)
- Better error rendering (422 field-level feedback)
- `/me` bootstrap on app load (persisted session UX)
- Dashboard UI shaping after contract/validation stabilization

## Prerequisites
- Docker Desktop (or Docker Engine + Compose plugin)
- Git

Optional for local frontend-only commands:
- Node.js + npm

## Setup

1. Clone:
```bash
git clone <repo-url>
cd ATHOS
```

2. Create root `.env` if missing:
```bash
cat > .env <<'EOF'
POSTGRES_USER=<db_user>
POSTGRES_PASSWORD=<db_password>
POSTGRES_DB=fitness
JWT_SECRET=<jwt_secret>
DATABASE_URL=postgresql+psycopg://<db_user>:<db_password>@db:5432/fitness
VITE_API_BASE_URL=http://localhost:8000
EOF
```

3. Start services from a clean slate:
```bash
docker compose down -v
docker compose up -d --build
docker compose exec backend alembic -c alembic.ini upgrade head
```

4. Check endpoints:
- Frontend: `http://localhost:5173`
- Backend health: `http://localhost:8000/health`

5. Run backend tests:
```bash
./backend_tests
```

## Walkthrough (Current App Behavior)

Use these commands to validate end-to-end behavior before frontend wiring:

1. Signup:
```bash
curl -sS -X POST http://localhost:8000/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"dev1@example.com","name":"Dev One","password":"AthosTest!1234","birth_year":1992,"birth_month":8}'
```
Note: steps 2, 4, and 5 should be tested through the front end UI for further product improvements at this time.

2. Login:
```bash
curl -sS -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"dev1@example.com","password":"AthosTest!1234"}'
```

3. Me:
```bash
curl -sS http://localhost:8000/v1/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

4. Create workout (omit `start_ts`; backend defaults to UTC now):
```bash
curl -sS -X POST http://localhost:8000/v1/workouts \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"workout_type":"STRENGTH","title":"Frontend readiness","strength_sets":[{"exercise_name":"Bench Press","weight":135,"reps":8}]}'
```

5. Dashboard read:
```bash
curl -sS "http://localhost:8000/v1/dashboard/day?date=2026-02-06&limit=50&top_k=10" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Client-Timezone: America/Los_Angeles"
```

6. Invalid timestamp check:
```bash
curl -sS -X POST http://localhost:8000/v1/workouts \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"workout_type":"STRENGTH","start_ts":"not-a-date","strength_sets":[{"exercise_name":"Bench Press","reps":8}]}'
```
Expected: `422`

## Frontend Env

- Frontend should read API URL from `import.meta.env.VITE_API_BASE_URL`.
- Minimal readiness files:
  - `frontend/.env.example`
  - `frontend/src/config.ts`
- No Vite proxy is required right now; backend CORS is already configured for local dev.

## Migrations

```bash
docker compose exec backend alembic -c alembic.ini upgrade head
docker compose exec backend alembic current
```

## Tests

Run all backend suites:
```bash
./backend_tests
```

Run a module:
```bash
./backend_tests -run observability
```

List modules:
```bash
./backend_tests --h
```

## Observability & Logs

- Logs go to stdout/stderr (no file logging).
- Response header `X-Request-ID` is always present.
- Canonical request log line comes from `athos.request` and includes:
  - `request_id`, `method`, `path`, `status_code`, `duration_ms`, `user_id`
- Example:
  - `INFO:athos.request:request_complete request_id=93170d3f-2ab9-49a9-aa2b-f4de0f06de44 method=GET path=/v1/workouts/... status_code=200 duration_ms=1.87 user_id=99`
- Uvicorn access logs may also appear separately.

Stream logs:
```bash
docker compose logs -f backend
```

## Stop

```bash
docker compose down
```

Remove local DB volume (destructive):
```bash
docker compose down -v
```
