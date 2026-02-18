from __future__ import annotations

import json
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4


class BackendTestBase(unittest.TestCase):
    base = "http://127.0.0.1:8000"
    tz = "America/Los_Angeles"

    def setUp(self):
        print(f"\n[TEST] running test for {self._testMethodName}\n")

    def tearDown(self):
        print("\n")
        time.sleep(3)
        print("\n")

    def _info(self, text: str):
        print(f"[INFO] {text}\n")

    def _fmt(self, value):
        if isinstance(value, (dict, list)):
            return json.dumps(value, indent=2, sort_keys=True, default=str)
        return str(value)

    def _pass(self, expected: str, received, expected_payload=None, received_payload=None):
        print("[PASS]")
        print(f"Expected: {expected}")
        print(f"Received: {received}")
        if expected_payload is not None:
            print("Expected Sample Payload:")
            print(self._fmt(expected_payload))
        if received_payload is not None:
            print("Received Payload:")
            print(self._fmt(received_payload))

    def _fail_with(self, expected: str, received):
        print("[FAIL]")
        print(f"Expected: {expected}")
        print(f"Received: {received}")
        self.fail(f"Expected: {expected} | Received: {received}")

    def _request(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
        token: str | None = None,
        include_tz: bool = True,
        tz_value: str | None = None,
    ) -> tuple[int, dict]:
        data = None if payload is None else json.dumps(payload).encode()
        req = Request(self.base + path, data=data, method=method)
        if payload is not None:
            req.add_header("Content-Type", "application/json")
        if token is not None:
            req.add_header("Authorization", f"Bearer {token}")
        if include_tz:
            req.add_header("X-Client-Timezone", tz_value or self.tz)

        try:
            with urlopen(req) as resp:
                body = resp.read().decode()
                return resp.status, json.loads(body) if body else {}
        except HTTPError as err:
            body = err.read().decode()
            try:
                parsed = json.loads(body) if body else {}
            except json.JSONDecodeError:
                parsed = {"raw": body}
            return err.code, parsed

    def _email(self, prefix: str) -> str:
        return f"{prefix}.{uuid4().hex[:12]}@example.com"

    def _password(self) -> str:
        return f"AthosTest!{uuid4().hex[:10]}"

    def _signup(self, email: str | None = None, password: str | None = None) -> tuple[str, str, str]:
        email = email or self._email("qa")
        password = password or self._password()
        status, body = self._request(
            "POST",
            "/v1/auth/signup",
            payload={
                "email": email,
                "name": "QA User",
                "password": password,
                "birth_year": 1992,
                "birth_month": 8,
            },
        )
        if status != 201:
            self._fail_with("201 from signup", {"status": status, "body": body})
        return email, password, body["access_token"]

    def _me(self, token: str) -> dict:
        status, body = self._request("GET", "/v1/auth/me", token=token, include_tz=False)
        if status != 200:
            self._fail_with("200 from /v1/auth/me", {"status": status, "body": body})
        return body

    def _create_strength_workout(
        self,
        token: str,
        start_ts: str,
        strength_sets: list[dict],
        title: str = "Strength",
        client_uuid: str | None = None,
    ) -> tuple[int, dict]:
        payload = {
            "workout_type": "STRENGTH",
            "title": title,
            "start_ts": start_ts,
            "strength_sets": strength_sets,
        }
        if client_uuid is not None:
            payload["client_uuid"] = client_uuid
        return self._request("POST", "/v1/workouts", payload=payload, token=token)

    def _create_cardio_workout(
        self,
        token: str,
        start_ts: str,
        cardio_session: dict,
        title: str = "Cardio",
    ) -> tuple[int, dict]:
        return self._request(
            "POST",
            "/v1/workouts",
            payload={
                "workout_type": "CARDIO",
                "title": title,
                "start_ts": start_ts,
                "cardio_session": cardio_session,
            },
            token=token,
        )
