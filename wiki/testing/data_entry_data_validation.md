# ATHOS Backend Data Entry DB Validation Runbook

This runbook is designed for an engineer with zero prior context. Run commands from repo root (`ATHOS/`).

## Test Areas

| Area | Name | Purpose | What It Proves |
|-----:|------|---------|----------------|
| 1 | Migration Determinism | Fresh DB rebuilds schema identically every time | Alembic correctness, indexes/constraints exist, no drift |
| 2 | Idempotent Write Behavior | Safe retries and multi-device sync | No duplicate workouts or child rows, conflict handling correct |
| 3 | User Isolation & Authorization | Multi-tenant security boundaries | Users cannot access or mutate other users’ data |
| 4 | Relational Integrity & Constraints | DB-level correctness enforcement | Unique constraints, FK integrity, cascade deletes |
| 5 | Exercise Normalization | Clean exercise dimension data | Case/whitespace reuse, canonical naming, no duplicates |
| 6 | Concurrency & Race Safety | Parallel writes behave safely | Unique constraint + retry logic prevents duplication |
| 7 | Timestamp Semantics | Auditing and ordering reliability | `created_at`/`updated_at` behavior is understood and validated |

## Prerequisites

- Docker Desktop running
- `.env` present in repo root (build it from the example in `README.md`)
- `curl` and `jq` installed locally

Load your local `.env` into the current shell so `$POSTGRES_USER` and `$POSTGRES_DB` are available:

```bash
set -a
source .env
set +a
```

## Environment Boot

Start core services:

```bash
docker compose up -d --build db backend
```

Check status:

```bash
docker compose ps
```

Expected:
- `fitness_db` is `healthy`
- `fitness_backend` is `up`

---

## AREA 1 — Migration Determinism

Goal:
- Confirm migrations are re-runnable and schema has no drift.

Run:

```bash
docker compose exec backend alembic -c alembic.ini upgrade head
docker compose exec backend alembic -c alembic.ini check
```

Expected:
- upgrade succeeds without error
- check prints: `No new upgrade operations detected.`

Validate critical schema objects:

```bash
docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\\d workouts"
docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\\d exercises"
docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\\d cardio_sessions"
docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\\d strength_sets"
```

Expected:
- `uq_workouts_user_client_uuid_not_null`
- `workouts_user_time` on `(user_id, start_ts DESC)`
- `uq_exercises_user_name_lower` on `(user_id, lower(name))`
- `cardio_sessions_workout_id_key` (one cardio row per workout)
- `strength_sets_workout_order` on `(workout_id, set_index)`

---

## AREA 2 — Idempotent Write Behavior

Goal:
- Confirm retries with identical `client_uuid` are safe and deduplicated.

Create a test user and token:

```bash
EMAIL="qa.$(date +%s)@example.com"
PASSWORD="AthosTest!$(date +%s)"

SIGNUP_RESP=$(curl -sS -X POST http://localhost:8000/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"name\":\"QA User\",\"password\":\"$PASSWORD\",\"birth_year\":1992,\"birth_month\":8}")

TOKEN=$(echo "$SIGNUP_RESP" | jq -r '.access_token')

echo "$SIGNUP_RESP"
```

Expected:
- signup returns HTTP `201`
- JSON contains `access_token`

Run idempotency test:

```bash
CLIENT_UUID=$(python3 - <<'PY'
import uuid
print(uuid.uuid4())
PY
)

REQ=$(cat <<JSON
{
  "workout_type": "STRENGTH",
  "title": "Idempotency QA",
  "start_ts": "2026-02-16T15:00:00Z",
  "client_uuid": "$CLIENT_UUID",
  "strength_sets": [
    {"exercise_name": "Squat", "set_index": 1, "weight": 225, "reps": 5},
    {"exercise_name": "Squat", "set_index": 2, "weight": 225, "reps": 5}
  ]
}
JSON
)

FIRST=$(curl -sS -w "\nHTTP:%{http_code}\n" -X POST http://localhost:8000/v1/workouts \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$REQ")
SECOND=$(curl -sS -w "\nHTTP:%{http_code}\n" -X POST http://localhost:8000/v1/workouts \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$REQ")

echo "$FIRST"
echo "$SECOND"
```

Expected:
- first request HTTP `201`
- second request HTTP `200`
- both responses have same `workout_id`
- second response has `strength_set_count: 0`

---

## AREA 3 — User Isolation & Authorization

Goal:
- Confirm one user cannot use another user’s exercise IDs.

Get user A profile and one exercise ID:

```bash
curl -sS http://localhost:8000/v1/auth/me -H "Authorization: Bearer $TOKEN"

USER_ID=$(curl -sS http://localhost:8000/v1/auth/me -H "Authorization: Bearer $TOKEN" | jq -r '.user_id')
EXERCISE_ID=$(docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -A -c "
SELECT id FROM exercises WHERE user_id = $USER_ID LIMIT 1;
" | tr -d '[:space:]')

echo "$EXERCISE_ID"
```

Create user B and attempt to post a workout using user A’s `exercise_id`:

```bash
EMAIL_B="qa.b.$(date +%s)@example.com"
PASSWORD_B="AthosTestB!$(date +%s)"

TOKEN_B=$(curl -sS -X POST http://localhost:8000/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL_B\",\"name\":\"QA User B\",\"password\":\"$PASSWORD_B\",\"birth_year\":1991,\"birth_month\":9}" \
  | jq -r '.access_token')

curl -sS -w "\nHTTP:%{http_code}\n" -X POST http://localhost:8000/v1/workouts \
  -H "Authorization: Bearer $TOKEN_B" \
  -H "Content-Type: application/json" \
  -d "{\"workout_type\":\"STRENGTH\",\"title\":\"Isolation\",\"start_ts\":\"2026-02-16T19:00:00Z\",\"strength_sets\":[{\"exercise_id\":\"$EXERCISE_ID\",\"set_index\":1,\"weight\":45,\"reps\":12}]}"
```

Expected:
- HTTP `404`
- body contains `{"detail":"Exercise not found"}`

---

## AREA 4 — Relational Integrity & Constraints

### Cardio uniqueness test

Goal:
- Verify each workout has at most one cardio detail row.

Create a cardio workout and capture ID:

```bash
CARDIO_WORKOUT_ID=$(curl -sS -X POST http://localhost:8000/v1/workouts \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "workout_type": "CARDIO",
    "title": "Cardio Uniqueness QA",
    "start_ts": "2026-02-16T13:00:00Z",
    "cardio_session": {"distance_miles": 3.1, "duration_seconds": 1800, "speed_mph": 6.2}
  }' | jq -r '.workout_id')

echo "$CARDIO_WORKOUT_ID"
```

Attempt duplicate child insert:

```bash
docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
SELECT count(*) AS cardio_rows_before
FROM cardio_sessions
WHERE workout_id = '$CARDIO_WORKOUT_ID';

INSERT INTO cardio_sessions (id, user_id, workout_id, created_at, updated_at)
SELECT gen_random_uuid(), user_id, '$CARDIO_WORKOUT_ID', now(), now()
FROM workouts
WHERE id = '$CARDIO_WORKOUT_ID';
"
```

Expected:
- `cardio_rows_before` is `1`
- insert fails with unique constraint violation on `workout_id`

### Cascade delete verification

Goal:
- Verify deleting a workout cascades to dependent `strength_sets` and `cardio_sessions` rows.

Strength cascade:

```bash
STRENGTH_WORKOUT_ID=$(curl -sS -X POST http://localhost:8000/v1/workouts \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "workout_type": "STRENGTH",
    "title": "Cascade Strength",
    "start_ts": "2026-02-16T20:00:00Z",
    "strength_sets": [{"exercise_name":"Cascade Lift","set_index":1,"weight":100,"reps":5}]
  }' | jq -r '.workout_id')

docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
SELECT count(*) AS child_count_before
FROM strength_sets
WHERE workout_id = '$STRENGTH_WORKOUT_ID';

DELETE FROM workouts
WHERE id = '$STRENGTH_WORKOUT_ID';

SELECT count(*) AS child_count_after
FROM strength_sets
WHERE workout_id = '$STRENGTH_WORKOUT_ID';
"
```

Cardio cascade:

```bash
CARDIO_WORKOUT_ID_2=$(curl -sS -X POST http://localhost:8000/v1/workouts \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "workout_type": "CARDIO",
    "title": "Cascade Cardio",
    "start_ts": "2026-02-16T20:30:00Z",
    "cardio_session": {"distance_miles": 1.0, "duration_seconds": 600}
  }' | jq -r '.workout_id')

docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
SELECT count(*) AS child_count_before
FROM cardio_sessions
WHERE workout_id = '$CARDIO_WORKOUT_ID_2';

DELETE FROM workouts
WHERE id = '$CARDIO_WORKOUT_ID_2';

SELECT count(*) AS child_count_after
FROM cardio_sessions
WHERE workout_id = '$CARDIO_WORKOUT_ID_2';
"
```

Expected:
- child count before delete is `> 0`
- child count after delete is `0`

---

## AREA 5 — Exercise Normalization

Goal:
- Verify same-user exercise reuse for case and leading/trailing whitespace variants.

Run:

```bash
curl -sS -X POST http://localhost:8000/v1/workouts \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "workout_type": "STRENGTH",
    "title": "Normalization 1",
    "start_ts": "2026-02-16T17:00:00Z",
    "strength_sets": [{"exercise_name":"Cable Row","set_index":1,"weight":90,"reps":10}]
  }' >/dev/null

curl -sS -X POST http://localhost:8000/v1/workouts \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "workout_type": "STRENGTH",
    "title": "Normalization 2",
    "start_ts": "2026-02-16T17:10:00Z",
    "strength_sets": [{"exercise_name":"cable row","set_index":1,"weight":95,"reps":8}]
  }' >/dev/null

curl -sS -X POST http://localhost:8000/v1/workouts \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "workout_type": "STRENGTH",
    "title": "Normalization 3",
    "start_ts": "2026-02-16T17:20:00Z",
    "strength_sets": [{"exercise_name":"  cable row  ","set_index":1,"weight":95,"reps":8}]
  }' >/dev/null

docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
SELECT COUNT(*) AS canonical_exercise_rows
FROM exercises
WHERE user_id = (SELECT user_id FROM users WHERE email = '$EMAIL')
  AND lower(name) LIKE '%cable row%';
"
```

Expected:
- `canonical_exercise_rows = 1`

---

## AREA 6 — Concurrency & Race Safety

Goal:
- Verify 20 parallel writes for same new exercise name all succeed with no duplicates.

Run:

```bash
docker compose exec backend python - <<'PY'
import json, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import Request, urlopen

base = "http://127.0.0.1:8000"
email = f"race.{int(time.time())}@example.com"
password = f"AthosTest!{int(time.time())}"
exercise_name = "Concurrency Bench"

def req(method, path, payload=None, token=None):
    data = None if payload is None else json.dumps(payload).encode()
    r = Request(base + path, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    with urlopen(r) as resp:
        return resp.status, json.loads(resp.read().decode())

_, signup = req("POST", "/v1/auth/signup", {
    "email": email,
    "name": "Race User",
    "password": password,
    "birth_year": 1990,
    "birth_month": 7,
})
token = signup["access_token"]

def post_once(i):
    body = {
        "workout_type": "STRENGTH",
        "title": f"Race {i}",
        "start_ts": "2026-02-16T16:00:00Z",
        "strength_sets": [
            {"exercise_name": exercise_name, "set_index": 1, "weight": 100, "reps": 10}
        ],
    }
    return req("POST", "/v1/workouts", body, token=token)

ok = 0
err = 0
with ThreadPoolExecutor(max_workers=20) as ex:
    futures = [ex.submit(post_once, i) for i in range(20)]
    for f in as_completed(futures):
        try:
            status, _ = f.result()
            if status == 201:
                ok += 1
            else:
                err += 1
        except Exception:
            err += 1

print(json.dumps({"ok_201": ok, "errors": err, "email": email, "exercise_name": exercise_name}))
PY
```

Use script output values to validate one exercise row exists:

```bash
docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
SELECT COUNT(*)
FROM exercises e
JOIN users u ON u.user_id = e.user_id
WHERE u.email = 'EMAIL_VALUE'
  AND lower(e.name) = lower('EXERCISE_NAME_VALUE');
"
```

Expected:
- script output has `ok_201 = 20` and `errors = 0`
- DB count query returns `1`

---

## AREA 7 — Timestamp Semantics

Goal:
- Validate how `created_at` and `updated_at` behave today in this stack.

Check insertion semantics:

```bash
docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
SELECT id, created_at, updated_at, (created_at = updated_at) AS same_on_insert
FROM workouts
ORDER BY created_at DESC
LIMIT 5;
"
```

Expected:
- both timestamps are populated on insert
- `same_on_insert` is `true` for new rows

Check direct SQL update semantics:

```bash
WORKOUT_ID_FOR_TS=$(docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -A -c "
SELECT id FROM workouts ORDER BY created_at DESC LIMIT 1;
" | tr -d '[:space:]')

docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
SELECT created_at, updated_at FROM workouts WHERE id = '$WORKOUT_ID_FOR_TS';
"

docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
UPDATE workouts SET title = 'Timestamp Probe' WHERE id = '$WORKOUT_ID_FOR_TS';
"

docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
SELECT created_at, updated_at FROM workouts WHERE id = '$WORKOUT_ID_FOR_TS';
"
```

Expected:
- direct SQL update may leave `updated_at` unchanged
- this confirms `updated_at` is not DB-trigger-managed today

---

## Optional Teardown

```bash
docker compose down
```

Destructive reset:

```bash
docker compose down -v
```
