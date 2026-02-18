# ATHOS Read Contract Raw Validation

## Prerequisites

- Backend and DB running via Docker Compose
- Valid JWT token for a test user

```bash
set -a
source .env
set +a

docker compose up -d db backend
```

Create token for testing:

```bash
EMAIL="read.qa.$(date +%s)@example.com"
PASSWORD="AthosRead!$(date +%s)"

SIGNUP=$(curl -sS -X POST http://localhost:8000/v1/auth/signup \
  -H "Content-Type: application/json" \
  -H "X-Client-Timezone: America/Los_Angeles" \
  -d "{\"email\":\"$EMAIL\",\"name\":\"Read QA\",\"password\":\"$PASSWORD\",\"birth_year\":1990,\"birth_month\":6}")

TOKEN=$(echo "$SIGNUP" | jq -r '.access_token')
echo "$TOKEN"
```

## Seed Sample Data (for reproducible read tests)

Populate the DB with your sample strength and cardio workouts for `2026-02-06`:

```bash
STRENGTH_CREATE_RESP=$(curl -sS -X POST http://localhost:8000/v1/workouts \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Client-Timezone: America/Los_Angeles" \
  -d '{
    "workout_type": "STRENGTH",
    "title": "Back + Shoulder + Chest",
    "start_ts": "2026-02-06T18:50:00Z",
    "strength_sets": [
      {"exercise_name":"Dead Hang","weight":185,"reps":1,"duration_seconds":60},
      {"exercise_name":"Lat Pulldowns (Bilateral)","weight":65,"reps":10},
      {"exercise_name":"Lat Pulldowns (Bilateral)","weight":105,"reps":10},
      {"exercise_name":"Lat Pulldowns (Bilateral)","weight":125,"reps":10},
      {"exercise_name":"Seated Cable Rows (Bilateral)","weight":45,"reps":10},
      {"exercise_name":"Seated Cable Rows (Bilateral)","weight":85,"reps":10},
      {"exercise_name":"Seated Cable Rows (Bilateral)","weight":125,"reps":10},
      {"exercise_name":"Cable Side Delt","weight":2.5,"reps":20},
      {"exercise_name":"Cable Side Delt","weight":5,"reps":20},
      {"exercise_name":"Cable Side Delt","weight":5,"reps":20},
      {"exercise_name":"Chest Flys (Peckdeck)","weight":60,"reps":10},
      {"exercise_name":"Chest Flys (Peckdeck)","weight":60,"reps":10},
      {"exercise_name":"Chest Flys (Peckdeck)","weight":60,"reps":10}
    ]
  }')

CARDIO_CREATE_RESP=$(curl -sS -X POST http://localhost:8000/v1/workouts \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Client-Timezone: America/Los_Angeles" \
  -d '{
    "workout_type": "CARDIO",
    "title": "Swim",
    "start_ts": "2026-02-06T22:30:00Z",
    "cardio_session": {
      "distance_miles": 0.6213711922,
      "duration_seconds": 1512
    }
  }')

echo "$STRENGTH_CREATE_RESP"
echo "$CARDIO_CREATE_RESP"

STRENGTH_WORKOUT_ID=$(echo "$STRENGTH_CREATE_RESP" | jq -r '.workout_id')
CARDIO_WORKOUT_ID=$(echo "$CARDIO_CREATE_RESP" | jq -r '.workout_id')
echo "$STRENGTH_WORKOUT_ID"
echo "$CARDIO_WORKOUT_ID"
```

Expected:
- both create requests return HTTP `201`
- one workout is STRENGTH with 13 sets
- one workout is CARDIO with one cardio detail row
- strength `set_index` values are auto-assigned in order (`1..13`)

## GET /v1/workouts

Request:

```bash
curl -sS "http://localhost:8000/v1/workouts?date=2026-02-06&limit=20" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Client-Timezone: America/Los_Angeles"
```

Representative response:

```json
[
  {
    "id": "CARDIO_WORKOUT_ID",
    "workout_type": "CARDIO",
    "title": "Swim",
    "start_ts": "2026-02-06T22:30:00Z",
    "end_ts": null,
    "source": null,
    "provider": null,
    "client_uuid": null,
    "strength_set_count": 0,
    "cardio_session_created": true
  },
  {
    "id": "STRENGTH_WORKOUT_ID",
    "workout_type": "STRENGTH",
    "title": "Back + Shoulder + Chest",
    "start_ts": "2026-02-06T18:50:00Z",
    "end_ts": null,
    "source": null,
    "provider": null,
    "client_uuid": null,
    "strength_set_count": 13,
    "cardio_session_created": false
  }
]
```

Expected behavior:
- HTTP 200
- Ordered by `start_ts` descending
- `strength_set_count` is computed from `strength_sets`
- `cardio_session_created` is true only when a cardio child exists
- No nested `strength_sets` or `cardio_session` payloads in this endpoint
- for this seeded sample day, list contains 2 workouts (CARDIO then STRENGTH)

Validation checks for the seeded sample:

```bash
LIST_RESP=$(curl -sS "http://localhost:8000/v1/workouts?date=2026-02-06&limit=20" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Client-Timezone: America/Los_Angeles")

echo "$LIST_RESP" | jq '. | length'
echo "$LIST_RESP" | jq '.[] | {workout_type, strength_set_count, cardio_session_created}'
```

Expected:
- list length is `2`
- CARDIO row has `strength_set_count: 0` and `cardio_session_created: true`
- STRENGTH row has `strength_set_count: 13` and `cardio_session_created: false`

Verify auto-assigned set ordering on detail:

```bash
curl -sS "http://localhost:8000/v1/workouts/$STRENGTH_WORKOUT_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Client-Timezone: America/Los_Angeles" \
  | jq '.strength_sets | map({exercise_name, set_index})'
```

Expected:
- `set_index` values are sequential (`1` through `13`) following payload row order

No workouts on that local date:

```bash
curl -i -sS "http://localhost:8000/v1/workouts?date=2099-01-01&limit=20" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Client-Timezone: America/Los_Angeles"
```

Expected:
- HTTP 200
- `[]`

Invalid timezone:

```bash
curl -i -sS "http://localhost:8000/v1/workouts?date=2026-02-06&limit=20" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Client-Timezone: Not/A_Real_TZ"
```

Expected:
- HTTP 422

## GET /v1/workouts/{id}

Get both workout ids from list response, then call detail:

```bash
LIST_RESP=$(curl -sS "http://localhost:8000/v1/workouts?date=2026-02-06&limit=20" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Client-Timezone: America/Los_Angeles")

STRENGTH_WORKOUT_ID=$(echo "$LIST_RESP" | jq -r '.[] | select(.workout_type=="STRENGTH") | .id')
CARDIO_WORKOUT_ID=$(echo "$LIST_RESP" | jq -r '.[] | select(.workout_type=="CARDIO") | .id')

curl -sS "http://localhost:8000/v1/workouts/$STRENGTH_WORKOUT_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Client-Timezone: America/Los_Angeles"

curl -sS "http://localhost:8000/v1/workouts/$CARDIO_WORKOUT_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Client-Timezone: America/Los_Angeles"
```

Representative STRENGTH response:

```json
{
  "id": "STRENGTH_WORKOUT_ID",
  "workout_type": "STRENGTH",
  "title": "Back + Shoulder + Chest",
  "start_ts": "2026-02-06T18:50:00Z",
  "end_ts": null,
  "source": null,
  "provider": null,
  "client_uuid": null,
  "strength_sets": [
    {
      "id": "SAMPLE_SET_ID",
      "workout_id": "STRENGTH_WORKOUT_ID",
      "exercise_id": "SAMPLE_EXERCISE_ID",
      "exercise_name": "Dead Hang",
      "set_index": 1,
      "weight": 185.0,
      "reps": 1,
      "duration_seconds": 60,
      "rpe": null,
      "notes": null
    }
  ],
  "cardio_session": null
}
```

Representative CARDIO response:

```json
{
  "id": "CARDIO_WORKOUT_ID",
  "workout_type": "CARDIO",
  "title": "Swim",
  "start_ts": "2026-02-06T22:30:00Z",
  "end_ts": null,
  "source": null,
  "provider": null,
  "client_uuid": null,
  "strength_sets": [],
  "cardio_session": {
    "id": "SAMPLE_CARDIO_ID",
    "workout_id": "CARDIO_WORKOUT_ID",
    "distance_miles": 0.6213711922,
    "duration_seconds": 1512,
    "incline": null,
    "speed_mph": null,
    "resistance": null,
    "rpms": null,
    "notes": null
  }
}
```

Expected behavior:
- HTTP 200 when workout belongs to caller
- STRENGTH includes `strength_sets` with `exercise_name`
- CARDIO includes `cardio_session`

## Auth and Scoping Expectations

Missing token:

```bash
curl -i -sS "http://localhost:8000/v1/workouts?date=2026-02-06&limit=20" \
  -H "X-Client-Timezone: America/Los_Angeles"
```

Expected:
- HTTP 401

Invalid token:

```bash
curl -i -sS "http://localhost:8000/v1/workouts?date=2026-02-06&limit=20" \
  -H "Authorization: Bearer invalid-token" \
  -H "X-Client-Timezone: America/Los_Angeles"
```

Expected:
- HTTP 401

Other user workout detail request:

```bash
EMAIL_B="read.other.$(date +%s)@example.com"
PASSWORD_B="AthosReadB!$(date +%s)"
TOKEN_B=$(curl -sS -X POST http://localhost:8000/v1/auth/signup \
  -H "Content-Type: application/json" \
  -H "X-Client-Timezone: America/Los_Angeles" \
  -d "{\"email\":\"$EMAIL_B\",\"name\":\"Read Other\",\"password\":\"$PASSWORD_B\",\"birth_year\":1991,\"birth_month\":7}" \
  | jq -r '.access_token')

curl -i -sS "http://localhost:8000/v1/workouts/$STRENGTH_WORKOUT_ID" \
  -H "Authorization: Bearer $TOKEN_B" \
  -H "X-Client-Timezone: America/Los_Angeles"
```

Expected:
- HTTP 404

## Timezone Semantics

For `GET /v1/workouts?date=YYYY-MM-DD`:
- API reads `X-Client-Timezone` as an IANA timezone
- Computes local day bounds `[00:00:00, next-day 00:00:00)` in that timezone
- Converts bounds to UTC
- Filters `workouts.start_ts` inside that UTC interval
- If header is omitted, UTC is used
