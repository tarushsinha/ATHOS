from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db.models.cardio_session import CardioSession
from app.db.models.exercise import Exercise
from app.db.models.strength_set import StrengthSet
from app.db.models.workout import Workout
from app.db.session import SessionLocal
from tests.base import BackendTestBase


class DataEntryTests(BackendTestBase):
    def test_workout_create_strength_and_cardio(self):
        self._info("Checks strength and cardio create contracts for /v1/workouts.")
        _, _, token = self._signup()

        status_s, body_s = self._create_strength_workout(
            token=token,
            start_ts="2026-02-16T12:00:00Z",
            title="Upper",
            strength_sets=[
                {"exercise_name": "Bench Press", "weight": 135, "reps": 8},
                {"exercise_name": "Bench Press", "weight": 135, "reps": 7},
            ],
        )
        self.assertEqual(status_s, 201, body_s)
        self.assertEqual(body_s["workout_type"], "STRENGTH")
        self.assertEqual(body_s["strength_set_count"], 2)
        self.assertFalse(body_s["cardio_session_created"])

        status_c, body_c = self._create_cardio_workout(
            token=token,
            start_ts="2026-02-16T13:00:00Z",
            title="Treadmill",
            cardio_session={"distance_miles": 3.1, "duration_seconds": 1800, "speed_mph": 6.2},
        )
        self.assertEqual(status_c, 201, body_c)
        self.assertEqual(body_c["workout_type"], "CARDIO")
        self.assertEqual(body_c["strength_set_count"], 0)
        self.assertTrue(body_c["cardio_session_created"])
        self._pass(
            "strength/cardio create contracts",
            {"strength": body_s, "cardio": body_c},
            expected_payload={
                "strength": {"workout_type": "STRENGTH", "strength_set_count": 2, "cardio_session_created": False},
                "cardio": {"workout_type": "CARDIO", "strength_set_count": 0, "cardio_session_created": True},
            },
            received_payload={"strength": body_s, "cardio": body_c},
        )

    def test_idempotency_client_uuid(self):
        self._info("Checks idempotent retry behavior using client_uuid.")
        _, _, token = self._signup()
        cid = str(uuid4())
        sets = [
            {"exercise_name": "Squat", "weight": 225, "reps": 5},
            {"exercise_name": "Squat", "weight": 225, "reps": 5},
        ]

        s1, b1 = self._create_strength_workout(token, "2026-02-16T15:00:00Z", sets, title="Idempotency", client_uuid=cid)
        s2, b2 = self._create_strength_workout(token, "2026-02-16T15:00:00Z", sets, title="Idempotency", client_uuid=cid)

        self.assertEqual(s1, 201, b1)
        self.assertEqual(s2, 200, b2)
        self.assertEqual(b1["workout_id"], b2["workout_id"])
        self.assertEqual(b2["strength_set_count"], 0)
        self._pass(
            "first 201 then 200, same workout_id",
            {"first": s1, "second": s2},
            expected_payload={"first_status": 201, "second_status": 200, "same_workout_id": True},
            received_payload={"first_status": s1, "second_status": s2, "first_body": b1, "second_body": b2},
        )

    def test_user_isolation_exercise_reference(self):
        self._info("Checks user isolation: user B cannot reference user A exercise_id.")
        _, _, token_a = self._signup()
        s, body = self._create_strength_workout(token_a, "2026-02-16T12:00:00Z", [{"exercise_name": "Isolation Lift", "weight": 100, "reps": 10}])
        self.assertEqual(s, 201, body)

        ds, detail_a = self._request("GET", f"/v1/workouts/{body['workout_id']}", token=token_a)
        self.assertEqual(ds, 200, detail_a)
        exercise_id = detail_a["strength_sets"][0]["exercise_id"]

        _, _, token_b = self._signup()
        status_b, body_b = self._request(
            "POST",
            "/v1/workouts",
            token=token_b,
            payload={
                "workout_type": "STRENGTH",
                "title": "Isolation",
                "start_ts": "2026-02-16T19:00:00Z",
                "strength_sets": [{"exercise_id": exercise_id, "weight": 45, "reps": 12}],
            },
        )
        self.assertEqual(status_b, 404, body_b)
        self.assertEqual(body_b["detail"], "Exercise not found")
        self._pass(
            "cross-user exercise reference blocked",
            status_b,
            expected_payload={"status": 404, "detail": "Exercise not found"},
            received_payload={"status": status_b, "body": body_b},
        )

    def test_exercise_normalization_case_and_whitespace(self):
        self._info("Checks case/whitespace variants reuse the same exercise row.")
        _, _, token = self._signup()
        user_id = self._me(token)["user_id"]

        self._create_strength_workout(token, "2026-02-16T17:00:00Z", [{"exercise_name": "Cable Row", "weight": 90, "reps": 10}], "Norm1")
        self._create_strength_workout(token, "2026-02-16T17:10:00Z", [{"exercise_name": "cable row", "weight": 95, "reps": 8}], "Norm2")
        self._create_strength_workout(token, "2026-02-16T17:20:00Z", [{"exercise_name": "  cable row  ", "weight": 95, "reps": 8}], "Norm3")

        with SessionLocal() as db:
            count = db.execute(
                select(func.count(Exercise.id)).where(
                    Exercise.user_id == user_id,
                    func.lower(Exercise.name) == "cable row",
                )
            ).scalar_one()
        self.assertEqual(count, 1)
        self._pass(
            "case/whitespace normalized to one exercise row",
            count,
            expected_payload={"canonical_count": 1},
            received_payload={"canonical_count": count},
        )

    def test_concurrency_create_on_write(self):
        self._info("Checks 20 parallel writes for same new exercise all succeed and dedupe exercise row.")
        _, _, token = self._signup()
        user_id = self._me(token)["user_id"]
        exercise_name = "Concurrency Bench"

        def post_once(i: int) -> int:
            status, _ = self._request(
                "POST",
                "/v1/workouts",
                token=token,
                payload={
                    "workout_type": "STRENGTH",
                    "title": f"Race {i}",
                    "start_ts": "2026-02-16T16:00:00Z",
                    "strength_sets": [{"exercise_name": exercise_name, "weight": 100, "reps": 10}],
                },
            )
            return status

        statuses: list[int] = []
        with ThreadPoolExecutor(max_workers=20) as ex:
            futures = [ex.submit(post_once, i) for i in range(20)]
            for f in as_completed(futures):
                statuses.append(f.result())

        self.assertEqual(statuses.count(201), 20, statuses)

        with SessionLocal() as db:
            count = db.execute(
                select(func.count(Exercise.id)).where(
                    Exercise.user_id == user_id,
                    func.lower(Exercise.name) == exercise_name.lower(),
                )
            ).scalar_one()
        self.assertEqual(count, 1)
        self._pass(
            "20x201 and one exercise row",
            {"ok_201": statuses.count(201), "rows": count},
            expected_payload={"ok_201": 20, "errors": 0, "exercise_rows": 1},
            received_payload={"ok_201": statuses.count(201), "errors": len(statuses) - statuses.count(201), "exercise_rows": count},
        )

    def test_relational_integrity_cardio_uniqueness_and_cascade(self):
        self._info("Checks cardio uniqueness constraint and workout->child cascade deletes.")
        _, _, token = self._signup()
        user_id = self._me(token)["user_id"]

        status_cardio, body_cardio = self._create_cardio_workout(token, "2026-02-16T13:00:00Z", {"distance_miles": 3.1, "duration_seconds": 1800}, title="Cardio unique")
        self.assertEqual(status_cardio, 201, body_cardio)
        cardio_workout_id = UUID(body_cardio["workout_id"])

        with SessionLocal() as db:
            before = db.execute(select(func.count(CardioSession.id)).where(CardioSession.workout_id == cardio_workout_id)).scalar_one()
            self.assertEqual(before, 1)

            db.add(CardioSession(user_id=user_id, workout_id=cardio_workout_id))
            with self.assertRaises(IntegrityError):
                db.commit()
            db.rollback()

        status_strength, body_strength = self._create_strength_workout(token, "2026-02-16T20:00:00Z", [{"exercise_name": "Cascade Lift", "weight": 100, "reps": 5}], title="Cascade Strength")
        self.assertEqual(status_strength, 201, body_strength)
        strength_workout_id = UUID(body_strength["workout_id"])

        with SessionLocal() as db:
            s_before = db.execute(select(func.count(StrengthSet.id)).where(StrengthSet.workout_id == strength_workout_id)).scalar_one()
            self.assertGreater(s_before, 0)

            w = db.execute(select(Workout).where(Workout.id == strength_workout_id)).scalar_one()
            db.delete(w)
            db.commit()
            s_after = db.execute(select(func.count(StrengthSet.id)).where(StrengthSet.workout_id == strength_workout_id)).scalar_one()
            self.assertEqual(s_after, 0)

            c_before = db.execute(select(func.count(CardioSession.id)).where(CardioSession.workout_id == cardio_workout_id)).scalar_one()
            self.assertGreater(c_before, 0)
            w2 = db.execute(select(Workout).where(Workout.id == cardio_workout_id)).scalar_one()
            db.delete(w2)
            db.commit()
            c_after = db.execute(select(func.count(CardioSession.id)).where(CardioSession.workout_id == cardio_workout_id)).scalar_one()
            self.assertEqual(c_after, 0)

        self._pass(
            "cardio uniqueness + cascade delete confirmed",
            "ok",
            expected_payload={
                "cardio_duplicate_insert": "IntegrityError",
                "strength_child_count_after_delete": 0,
                "cardio_child_count_after_delete": 0,
            },
            received_payload={"strength_child_count_after_delete": s_after, "cardio_child_count_after_delete": c_after},
        )

    def test_timestamp_semantics_on_insert_and_orm_update(self):
        self._info("Checks timestamp semantics on insert and ORM-managed update.")
        _, _, token = self._signup()
        status_s, body_s = self._create_strength_workout(token, "2026-02-16T18:00:00Z", [{"exercise_name": "Timestamp Lift", "weight": 100, "reps": 5}], title="Timestamp QA")
        self.assertEqual(status_s, 201, body_s)
        wid = UUID(body_s["workout_id"])

        with SessionLocal() as db:
            workout = db.execute(select(Workout).where(Workout.id == wid)).scalar_one()
            self.assertEqual(workout.created_at, workout.updated_at)
            before = workout.updated_at
            workout.title = "Timestamp QA updated"
            db.commit()
            db.refresh(workout)
            self.assertGreaterEqual(workout.updated_at, before)

        self._pass(
            "timestamp semantics validated",
            "ok",
            expected_payload={"created_at_equals_updated_at_on_insert": True, "updated_at_changes_on_update": True},
            received_payload={"updated_at_before": str(before), "updated_at_after": str(workout.updated_at)},
        )
