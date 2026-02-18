from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select

from app.db.models.muscle_group import ExerciseMuscleMap, MuscleGroup
from app.db.session import SessionLocal
from app.schemas.dashboard import DashboardDayResponse
from tests.base import BackendTestBase


class DashboardContractTests(BackendTestBase):
    def test_dashboard_day_contract(self):
        self._info("Checks /v1/dashboard/day populated and empty responses, plus auth and timezone error behavior.")
        _, _, token = self._signup()

        self._create_strength_workout(
            token,
            "2026-02-06T18:50:00Z",
            [
                {"exercise_name": "Dead Hang", "weight": 185, "reps": 1, "duration_seconds": 60},
                {"exercise_name": "Lat Pulldowns (Bilateral)", "weight": 125, "reps": 10},
            ],
            title="Dashboard Strength",
        )
        self._create_cardio_workout(
            token,
            "2026-02-06T22:30:00Z",
            {"distance_miles": 0.6213711922, "duration_seconds": 1512},
            title="Swim",
        )

        status_ok, body = self._request("GET", "/v1/dashboard/day?date=2026-02-06&limit=50&top_k=10", token=token)
        self.assertEqual(status_ok, 200, body)
        self.assertIn("workouts", body)
        self.assertIn("telemetry", body)
        self.assertEqual(len(body["workouts"]), 2)

        telemetry = body["telemetry"]
        self.assertIn("total_training_load", telemetry)
        self.assertIn("best_set_load", telemetry)
        self.assertIn("best_set_exercise_name", telemetry)
        self.assertIn("max_weight_per_exercise", telemetry)
        self.assertIn("muscle_group_training_load", telemetry)
        self.assertIn("cardio_totals", telemetry)

        status_empty, empty = self._request("GET", "/v1/dashboard/day?date=2099-01-01", token=token)
        self.assertEqual(status_empty, 200, empty)
        self.assertEqual(empty["workouts"], [])
        self.assertEqual(empty["telemetry"]["total_training_load"], 0.0)
        self.assertIsNone(empty["telemetry"]["best_set_load"])
        self.assertIsNone(empty["telemetry"]["best_set_exercise_name"])
        self.assertEqual(empty["telemetry"]["max_weight_per_exercise"], [])
        self.assertEqual(empty["telemetry"]["muscle_group_training_load"], [])
        self.assertEqual(empty["telemetry"]["cardio_totals"]["total_distance_miles"], 0.0)
        self.assertIsNone(empty["telemetry"]["cardio_totals"]["total_duration_seconds"])

        status_missing, _ = self._request("GET", "/v1/dashboard/day?date=2026-02-06", include_tz=True)
        self.assertEqual(status_missing, 401)
        status_invalid, _ = self._request("GET", "/v1/dashboard/day?date=2026-02-06", token="invalid-token")
        self.assertEqual(status_invalid, 401)
        status_bad_tz, _ = self._request("GET", "/v1/dashboard/day?date=2026-02-06", token=token, tz_value="Not/A_Real_TZ")
        self.assertEqual(status_bad_tz, 422)

        self._pass(
            "dashboard populated/empty/auth/tz contract",
            "ok",
            expected_payload={
                "populated": {"workouts": "<non-empty>", "telemetry": {"total_training_load": "<float>"}},
                "empty": {"workouts": [], "telemetry": {"total_training_load": 0.0, "best_set_load": None}},
                "missing_auth_status": 401,
                "invalid_auth_status": 401,
                "invalid_tz_status": 422,
            },
            received_payload={
                "populated": body,
                "empty": empty,
                "missing_auth_status": status_missing,
                "invalid_auth_status": status_invalid,
                "invalid_tz_status": status_bad_tz,
            },
        )

    def test_dashboard_muscle_group_primary_attribution(self):
        self._info("Checks muscle group attribution uses primary mappings when present.")
        _, _, token = self._signup()

        s, created = self._create_strength_workout(
            token,
            "2026-02-06T18:50:00Z",
            [{"exercise_name": "Mapped Lift", "weight": 100, "reps": 10}],
            title="Mapped",
        )
        self.assertEqual(s, 201, created)

        d, detail = self._request("GET", f"/v1/workouts/{created['workout_id']}", token=token)
        self.assertEqual(d, 200, detail)
        exercise_id = UUID(detail["strength_sets"][0]["exercise_id"])

        with SessionLocal() as db:
            mg_primary = MuscleGroup(name=f"Back-{uuid4().hex[:8]}")
            mg_secondary = MuscleGroup(name=f"Shoulder-{uuid4().hex[:8]}")
            db.add_all([mg_primary, mg_secondary])
            db.flush()

            db.add_all(
                [
                    ExerciseMuscleMap(exercise_id=exercise_id, muscle_group_id=mg_primary.id, is_primary=True),
                    ExerciseMuscleMap(exercise_id=exercise_id, muscle_group_id=mg_secondary.id, is_primary=False),
                ]
            )
            db.commit()
            primary_name = mg_primary.name
            secondary_name = mg_secondary.name

        sd, dash = self._request("GET", "/v1/dashboard/day?date=2026-02-06&limit=50&top_k=10", token=token)
        self.assertEqual(sd, 200, dash)

        mapped_set = None
        for w in dash["workouts"]:
            for sset in w.get("strength_sets", []):
                if sset.get("exercise_name") == "Mapped Lift":
                    mapped_set = sset
                    break
            if mapped_set:
                break

        self.assertIsNotNone(mapped_set)
        self.assertIn(primary_name, mapped_set["muscle_groups"])
        self.assertNotIn(secondary_name, mapped_set["muscle_groups"])

        mg_load = {row["muscle_group"]: row["load"] for row in dash["telemetry"]["muscle_group_training_load"]}
        self.assertIn(primary_name, mg_load)
        self.assertNotIn(secondary_name, mg_load)

        self._pass(
            "primary-only attribution when primary exists",
            mg_load,
            expected_payload={"muscle_groups_on_set": [primary_name], "telemetry_includes": [primary_name], "telemetry_excludes": [secondary_name]},
            received_payload={"muscle_groups_on_set": mapped_set["muscle_groups"], "telemetry": dash["telemetry"]["muscle_group_training_load"]},
        )

    def test_dashboard_schema_serialization_shape(self):
        self._info("Checks DashboardDayResponse schema validates and serializes expected keys.")
        payload = DashboardDayResponse.model_validate(
            {
                "workouts": [
                    {
                        "id": "00000000-0000-0000-0000-000000000001",
                        "workout_type": "STRENGTH",
                        "title": "Session",
                        "start_ts": "2026-02-06T10:00:00Z",
                        "end_ts": None,
                        "source": None,
                        "provider": None,
                        "client_uuid": None,
                        "strength_sets": [
                            {
                                "id": "00000000-0000-0000-0000-000000000010",
                                "workout_id": "00000000-0000-0000-0000-000000000001",
                                "exercise_id": "00000000-0000-0000-0000-000000000099",
                                "exercise_name": "Dead Hang",
                                "set_index": 1,
                                "weight": 185.0,
                                "reps": 1,
                                "duration_seconds": 60,
                                "rpe": None,
                                "notes": None,
                                "muscle_groups": ["Back"],
                            }
                        ],
                        "cardio_session": None,
                    }
                ],
                "telemetry": {
                    "total_training_load": 185.0,
                    "best_set_load": 185.0,
                    "best_set_exercise_name": "Dead Hang",
                    "max_weight_per_exercise": [{"exercise_name": "Dead Hang", "max_weight": 185.0}],
                    "muscle_group_training_load": [{"muscle_group": "Back", "load": 185.0}],
                    "cardio_totals": {"total_distance_miles": 0.0, "total_duration_seconds": None},
                },
            }
        )

        output = payload.model_dump(mode="json")
        self.assertIn("workouts", output)
        self.assertIn("telemetry", output)
        self.assertEqual(output["workouts"][0]["strength_sets"][0]["muscle_groups"], ["Back"])

        self._pass(
            "dashboard schema validate/serialize",
            "ok",
            expected_payload={"keys": ["workouts", "telemetry"], "muscle_groups": ["Back"]},
            received_payload=output,
        )
