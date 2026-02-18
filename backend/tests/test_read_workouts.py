from __future__ import annotations

from tests.base import BackendTestBase


class ReadWorkoutsContractTests(BackendTestBase):
    def test_read_workouts_list_contract(self):
        self._info("Checks /v1/workouts list contract, ordering, flags, auth and timezone handling.")
        _, _, token = self._signup()

        s1, b1 = self._create_strength_workout(
            token,
            "2026-02-06T18:50:00Z",
            [{"exercise_name": "Dead Hang", "weight": 185, "reps": 1, "duration_seconds": 60}],
            title="Back + Shoulder + Chest",
        )
        self.assertEqual(s1, 201, b1)

        s2, b2 = self._create_cardio_workout(
            token,
            "2026-02-06T22:30:00Z",
            {"distance_miles": 0.6213711922, "duration_seconds": 1512},
            title="Swim",
        )
        self.assertEqual(s2, 201, b2)

        status, items = self._request("GET", "/v1/workouts?date=2026-02-06&limit=20", token=token)
        self.assertEqual(status, 200, items)
        self.assertEqual(len(items), 2)
        self.assertGreaterEqual(items[0]["start_ts"], items[1]["start_ts"])

        forbidden = {"user_id", "version", "created_at", "updated_at", "strength_sets", "cardio_session"}
        for item in items:
            self.assertFalse(any(k in item for k in forbidden), item)
            self.assertIn("strength_set_count", item)
            self.assertIn("cardio_session_created", item)

        types = {i["workout_type"]: i for i in items}
        self.assertEqual(types["CARDIO"]["strength_set_count"], 0)
        self.assertTrue(types["CARDIO"]["cardio_session_created"])
        self.assertEqual(types["STRENGTH"]["strength_set_count"], 1)
        self.assertFalse(types["STRENGTH"]["cardio_session_created"])

        status_empty, body_empty = self._request("GET", "/v1/workouts?date=2099-01-01&limit=20", token=token)
        self.assertEqual(status_empty, 200)
        self.assertEqual(body_empty, [])

        status_bad_tz, _ = self._request("GET", "/v1/workouts?date=2026-02-06&limit=20", token=token, tz_value="Not/A_Real_TZ")
        self.assertEqual(status_bad_tz, 422)

        status_no_auth, _ = self._request("GET", "/v1/workouts?date=2026-02-06&limit=20", include_tz=True)
        self.assertEqual(status_no_auth, 401)

        status_bad_auth, _ = self._request("GET", "/v1/workouts?date=2026-02-06&limit=20", token="invalid-token")
        self.assertEqual(status_bad_auth, 401)

        self._pass(
            "/v1/workouts list contract checks",
            "ok",
            expected_payload={
                "items": [
                    {"workout_type": "CARDIO", "strength_set_count": 0, "cardio_session_created": True},
                    {"workout_type": "STRENGTH", "strength_set_count": 1, "cardio_session_created": False},
                ],
                "empty_day_status": 200,
                "empty_day_payload": [],
                "bad_tz_status": 422,
                "missing_auth_status": 401,
                "invalid_auth_status": 401,
            },
            received_payload={
                "items": items,
                "empty_day_status": status_empty,
                "empty_day_payload": body_empty,
                "bad_tz_status": status_bad_tz,
                "missing_auth_status": status_no_auth,
                "invalid_auth_status": status_bad_auth,
            },
        )

    def test_read_workout_detail_contract_and_scoping(self):
        self._info("Checks /v1/workouts/{id} detail payload for strength/cardio and cross-user scoping 404.")
        _, _, token_a = self._signup()

        s1, b1 = self._create_strength_workout(
            token_a,
            "2026-02-06T18:50:00Z",
            [
                {"exercise_name": "Dead Hang", "weight": 185, "reps": 1, "duration_seconds": 60},
                {"exercise_name": "Lat Pulldowns (Bilateral)", "weight": 125, "reps": 10},
            ],
            title="Strength",
        )
        self.assertEqual(s1, 201, b1)

        s2, b2 = self._create_cardio_workout(
            token_a,
            "2026-02-06T22:30:00Z",
            {"distance_miles": 0.6213711922, "duration_seconds": 1512},
            title="Swim",
        )
        self.assertEqual(s2, 201, b2)

        ds, js = self._request("GET", f"/v1/workouts/{b1['workout_id']}", token=token_a)
        self.assertEqual(ds, 200, js)
        self.assertEqual(js["workout_type"], "STRENGTH")
        self.assertIsNone(js["cardio_session"])
        self.assertGreaterEqual(len(js["strength_sets"]), 2)
        self.assertIn("exercise_name", js["strength_sets"][0])
        self.assertNotIn("user_id", js)

        dc, jc = self._request("GET", f"/v1/workouts/{b2['workout_id']}", token=token_a)
        self.assertEqual(dc, 200, jc)
        self.assertEqual(jc["workout_type"], "CARDIO")
        self.assertEqual(jc["strength_sets"], [])
        self.assertIsNotNone(jc["cardio_session"])

        _, _, token_b = self._signup()
        status_other, _ = self._request("GET", f"/v1/workouts/{b1['workout_id']}", token=token_b)
        self.assertEqual(status_other, 404)

        self._pass(
            "/v1/workouts/{id} detail + cross-user 404",
            "ok",
            expected_payload={
                "strength_detail": {"workout_type": "STRENGTH", "cardio_session": None, "strength_sets": [{"exercise_name": "<name>"}]},
                "cardio_detail": {"workout_type": "CARDIO", "strength_sets": [], "cardio_session": {"distance_miles": "<number>"}},
                "cross_user_status": 404,
            },
            received_payload={"strength_detail": js, "cardio_detail": jc, "cross_user_status": status_other},
        )

    def test_set_index_auto_assignment_and_order(self):
        self._info("Checks set_index auto-assignment follows payload order when set_index is omitted.")
        _, _, token = self._signup()
        s, b = self._create_strength_workout(
            token,
            "2026-02-06T18:50:00Z",
            [
                {"exercise_name": "Dead Hang", "weight": 185, "reps": 1, "duration_seconds": 60},
                {"exercise_name": "Lat Pulldowns (Bilateral)", "weight": 65, "reps": 10},
                {"exercise_name": "Lat Pulldowns (Bilateral)", "weight": 105, "reps": 10},
            ],
            title="Auto set index",
        )
        self.assertEqual(s, 201, b)

        d, body = self._request("GET", f"/v1/workouts/{b['workout_id']}", token=token)
        self.assertEqual(d, 200, body)
        set_indexes = [x["set_index"] for x in body["strength_sets"]]
        self.assertEqual(set_indexes, [1, 2, 3])

        self._pass(
            "set_index auto-assigned in order",
            set_indexes,
            expected_payload={"set_indexes": [1, 2, 3]},
            received_payload={"set_indexes": set_indexes, "detail": body},
        )
