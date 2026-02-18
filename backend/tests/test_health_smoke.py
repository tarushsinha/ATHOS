from __future__ import annotations

from sqlalchemy import inspect

from app.db.session import SessionLocal
from tests.base import BackendTestBase


class HealthAndSmokeTests(BackendTestBase):
    def test_health_endpoints(self):
        self._info("Checks /health and /health/db basic service smoke endpoints.")
        s1, b1 = self._request("GET", "/health", include_tz=False)
        self.assertEqual(s1, 200)
        self.assertEqual(b1.get("status"), "ok")
        self._pass("200 + status=ok", b1)

        s2, b2 = self._request("GET", "/health/db", include_tz=False)
        self.assertEqual(s2, 200)
        self.assertEqual(b2.get("db"), "ok")
        self._pass(
            "200 + db=ok",
            b2,
            expected_payload={"health": {"status": "ok"}, "health_db": {"db": "ok"}},
            received_payload={"health": b1, "health_db": b2},
        )

    def test_schema_indexes_constraints_exist(self):
        self._info("Checks expected DB indexes/constraints exist for current schema contract.")
        with SessionLocal() as db:
            ins = inspect(db.bind)
            workout_indexes = {i["name"] for i in ins.get_indexes("workouts")}
            exercise_indexes = {i["name"] for i in ins.get_indexes("exercises")}
            strength_indexes = {i["name"] for i in ins.get_indexes("strength_sets")}
            cardio_indexes = {i["name"] for i in ins.get_indexes("cardio_sessions")}
            cardio_uniques = {u["name"] for u in ins.get_unique_constraints("cardio_sessions")}

        self.assertIn("workouts_user_time", workout_indexes)
        self.assertIn("uq_workouts_user_client_uuid_not_null", workout_indexes)
        self.assertIn("uq_exercises_user_name_lower", exercise_indexes)
        self.assertIn("strength_sets_workout_order", strength_indexes)
        self.assertIn("cardio_sessions_user_time", cardio_indexes)
        self.assertIn("cardio_sessions_workout_id_key", cardio_uniques)
        self._pass(
            "expected core indexes/constraints present",
            "ok",
            expected_payload={
                "workouts": ["workouts_user_time", "uq_workouts_user_client_uuid_not_null"],
                "exercises": ["uq_exercises_user_name_lower"],
                "strength_sets": ["strength_sets_workout_order"],
                "cardio_sessions": ["cardio_sessions_user_time", "cardio_sessions_workout_id_key"],
            },
            received_payload={
                "workouts": sorted(workout_indexes),
                "exercises": sorted(exercise_indexes),
                "strength_sets": sorted(strength_indexes),
                "cardio_sessions_indexes": sorted(cardio_indexes),
                "cardio_sessions_uniques": sorted(cardio_uniques),
            },
        )
