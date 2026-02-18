# ATHOS Dashboard Day Read Contract Validation

## Endpoint

`GET /v1/dashboard/day?date=YYYY-MM-DD`

## Prerequisites

```bash
set -a
source .env
set +a

docker compose up -d db backend
```

Create test token:

```bash
EMAIL="dash.qa.$(date +%s)@example.com"
PASSWORD="AthosDash!$(date +%s)"

TOKEN=$(curl -sS -X POST http://localhost:8000/v1/auth/signup \
  -H "Content-Type: application/json" \
  -H "X-Client-Timezone: America/Los_Angeles" \
  -d "{\"email\":\"$EMAIL\",\"name\":\"Dashboard QA\",\"password\":\"$PASSWORD\",\"birth_year\":1992,\"birth_month\":8}" \
  | jq -r '.access_token')

echo "$TOKEN"
```

Seed one strength and one cardio workout for `2026-02-06`:

```bash
curl -sS -X POST http://localhost:8000/v1/workouts \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Client-Timezone: America/Los_Angeles" \
  -d '{
    "workout_type": "STRENGTH",
    "title": "Dashboard Strength",
    "start_ts": "2026-02-06T18:50:00Z",
    "strength_sets": [
      {"exercise_name":"Dead Hang","weight":185,"reps":1,"duration_seconds":60},
      {"exercise_name":"Lat Pulldowns (Bilateral)","weight":125,"reps":10}
    ]
  }'

curl -sS -X POST http://localhost:8000/v1/workouts \
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
  }'
```

## Curl Example

```bash
curl -sS "http://localhost:8000/v1/dashboard/day?date=2026-02-06&limit=50&top_k=10" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Client-Timezone: America/Los_Angeles"
```

## Representative Response

```json
{
  "workouts": [
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
        "id": "CARDIO_SESSION_ID",
        "workout_id": "CARDIO_WORKOUT_ID",
        "distance_miles": 0.6213711922,
        "duration_seconds": 1512,
        "incline": null,
        "speed_mph": null,
        "resistance": null,
        "rpms": null,
        "notes": null
      }
    },
    {
      "id": "STRENGTH_WORKOUT_ID",
      "workout_type": "STRENGTH",
      "title": "Dashboard Strength",
      "start_ts": "2026-02-06T18:50:00Z",
      "end_ts": null,
      "source": null,
      "provider": null,
      "client_uuid": null,
      "strength_sets": [
        {
          "id": "SET_ID",
          "workout_id": "STRENGTH_WORKOUT_ID",
          "exercise_id": "EXERCISE_ID",
          "exercise_name": "Dead Hang",
          "set_index": 1,
          "weight": 185.0,
          "reps": 1,
          "duration_seconds": 60,
          "rpe": null,
          "notes": null,
          "muscle_groups": []
        }
      ],
      "cardio_session": null
    }
  ],
  "telemetry": {
    "total_training_load": 1435.0,
    "best_set_load": 1250.0,
    "best_set_exercise_name": "Lat Pulldowns (Bilateral)",
    "max_weight_per_exercise": [
      {"exercise_name": "Dead Hang", "max_weight": 185.0},
      {"exercise_name": "Lat Pulldowns (Bilateral)", "max_weight": 125.0}
    ],
    "muscle_group_training_load": [],
    "cardio_totals": {
      "total_distance_miles": 0.6213711922,
      "total_duration_seconds": 1512
    }
  }
}
```

## Expected Behaviors

Missing token:

```bash
curl -i -sS "http://localhost:8000/v1/dashboard/day?date=2026-02-06" \
  -H "X-Client-Timezone: America/Los_Angeles"
```

Expected:
- HTTP 401

Invalid token:

```bash
curl -i -sS "http://localhost:8000/v1/dashboard/day?date=2026-02-06" \
  -H "Authorization: Bearer invalid-token" \
  -H "X-Client-Timezone: America/Los_Angeles"
```

Expected:
- HTTP 401

No workouts that day:

```bash
curl -sS "http://localhost:8000/v1/dashboard/day?date=2099-01-01" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Client-Timezone: America/Los_Angeles"
```

Expected:
- HTTP 200
- `workouts` is `[]`
- telemetry:
  - `total_training_load = 0`
  - `best_set_load = null`
  - `best_set_exercise_name = null`
  - `max_weight_per_exercise = []`
  - `muscle_group_training_load = []`
  - `cardio_totals.total_distance_miles = 0`
  - `cardio_totals.total_duration_seconds = null`

Invalid timezone:

```bash
curl -i -sS "http://localhost:8000/v1/dashboard/day?date=2026-02-06" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Client-Timezone: Not/A_Real_TZ"
```

Expected:
- HTTP 422

## Muscle Group Attribution Rule

Telemetry uses this rule for `muscle_group_training_load`:
- If an exercise has one or more mappings marked `is_primary = true`, load is attributed only to those primary muscle groups.
- If no primary mapping exists, load is attributed to all mapped muscle groups.
- If an exercise has no muscle group mapping rows, that set contributes no load to `muscle_group_training_load`.
