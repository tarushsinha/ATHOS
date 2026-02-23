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

    def test_cors_preflight_workouts_and_dashboard(self):
        self._info("Checks CORS preflight for Vite dev origin on workouts and dashboard endpoints.")
        common_headers = {
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization, Content-Type, X-Client-Timezone",
        }

        s_w, b_w = self._request("OPTIONS", "/v1/workouts", include_tz=False)
        s_d, b_d = self._request("OPTIONS", "/v1/dashboard/day", include_tz=False)

        # Use low-level requests with CORS headers to validate middleware response headers.
        from urllib.request import Request, urlopen

        req_w = Request(self.base + "/v1/workouts", method="OPTIONS")
        req_d = Request(self.base + "/v1/dashboard/day", method="OPTIONS")
        for k, v in common_headers.items():
            req_w.add_header(k, v)
            req_d.add_header(k, v)

        with urlopen(req_w) as rw:
            hw = {k.lower(): v for k, v in rw.headers.items()}
            status_w = rw.status
        with urlopen(req_d) as rd:
            hd = {k.lower(): v for k, v in rd.headers.items()}
            status_d = rd.status

        self.assertIn(status_w, (200, 204))
        self.assertIn(status_d, (200, 204))
        self.assertEqual(hw.get("access-control-allow-origin"), "http://localhost:5173")
        self.assertEqual(hd.get("access-control-allow-origin"), "http://localhost:5173")
        self.assertIn("post", hw.get("access-control-allow-methods", "").lower())
        self.assertIn("post", hd.get("access-control-allow-methods", "").lower())
        self.assertIn("authorization", hw.get("access-control-allow-headers", "").lower())
        self.assertIn("content-type", hw.get("access-control-allow-headers", "").lower())
        self.assertIn("x-client-timezone", hw.get("access-control-allow-headers", "").lower())
        self.assertIn("authorization", hd.get("access-control-allow-headers", "").lower())
        self.assertIn("content-type", hd.get("access-control-allow-headers", "").lower())
        self.assertIn("x-client-timezone", hd.get("access-control-allow-headers", "").lower())

        self._pass(
            "OPTIONS preflight succeeds with expected CORS allow-* headers",
            "ok",
            expected_payload={
                "status_workouts": "200 or 204",
                "status_dashboard": "200 or 204",
                "allow_origin": "http://localhost:5173",
                "allow_methods_contains": ["POST"],
                "allow_headers_contains": ["Authorization", "Content-Type", "X-Client-Timezone"],
            },
            received_payload={
                "status_workouts": status_w,
                "status_dashboard": status_d,
                "headers_workouts": hw,
                "headers_dashboard": hd,
                "status_without_cors_headers_workouts": s_w,
                "status_without_cors_headers_dashboard": s_d,
                "body_without_cors_headers_workouts": b_w,
                "body_without_cors_headers_dashboard": b_d,
            },
        )
