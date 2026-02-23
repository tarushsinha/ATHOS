from __future__ import annotations

import asyncio
import json
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

from starlette.requests import Request as StarletteRequest
from starlette.responses import PlainTextResponse

from app.middleware.request_logging import RequestLoggingMiddleware
from tests.base import BackendTestBase


class ObservabilityTests(BackendTestBase):
    def _raw_request(
        self,
        method: str,
        path: str,
        headers: dict[str, str] | None = None,
        payload: dict | None = None,
    ) -> tuple[int, dict, dict]:
        data = None if payload is None else json.dumps(payload).encode()
        req = Request(self.base + path, method=method, data=data)
        if payload is not None:
            req.add_header("Content-Type", "application/json")
        for key, value in (headers or {}).items():
            req.add_header(key, value)

        try:
            with urlopen(req) as resp:
                body = resp.read().decode()
                payload = json.loads(body) if body else {}
                return resp.status, payload, {k.lower(): v for k, v in resp.headers.items()}
        except HTTPError as err:
            body = err.read().decode()
            payload = json.loads(body) if body else {}
            return err.code, payload, {k.lower(): v for k, v in err.headers.items()}

    def test_healthz_endpoint(self):
        self._info("Checks /healthz readiness endpoint exists and returns status ok.")
        status, body, _ = self._raw_request("GET", "/healthz")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"status": "ok"})
        self._pass(
            "200 with {'status':'ok'}",
            body,
            expected_payload={"status": "ok"},
            received_payload=body,
        )

    def test_request_id_header_auto_generated(self):
        self._info("Checks middleware adds X-Request-ID when client does not provide one.")
        status, body, headers = self._raw_request("GET", "/health")
        self.assertEqual(status, 200, body)
        self.assertTrue(headers.get("x-request-id"))
        self._pass(
            "response contains generated X-Request-ID",
            "ok",
            expected_payload={"status": 200, "x-request-id": "<uuid>"},
            received_payload={"status": status, "x-request-id": headers.get("x-request-id"), "body": body},
        )

    def test_request_id_header_passthrough_on_unauthorized(self):
        self._info("Checks middleware preserves provided X-Request-ID even on 401 responses.")
        request_id = str(uuid4())
        status, body, headers = self._raw_request(
            "GET",
            "/v1/workouts?date=2026-02-16&limit=20",
            headers={
                "X-Request-ID": request_id,
                "X-Client-Timezone": self.tz,
            },
        )
        self.assertEqual(status, 401, body)
        self.assertEqual(headers.get("x-request-id"), request_id)
        self._pass(
            "provided X-Request-ID is echoed on unauthorized response",
            "ok",
            expected_payload={"status": 401, "x-request-id": request_id},
            received_payload={"status": status, "x-request-id": headers.get("x-request-id"), "body": body},
        )

    def test_request_id_header_present_on_422(self):
        self._info("Checks middleware includes X-Request-ID on 422 validation responses.")
        _, _, token = self._signup()
        request_id = str(uuid4())
        status, body, headers = self._raw_request(
            "POST",
            "/v1/workouts",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Request-ID": request_id,
                "X-Client-Timezone": self.tz,
            },
            payload={
                "workout_type": "STRENGTH",
                "title": "Bad timestamp",
                "start_ts": "not-a-date",
                "strength_sets": [{"exercise_name": "Bench", "reps": 10}],
            },
        )
        self.assertEqual(status, 422, body)
        self.assertEqual(headers.get("x-request-id"), request_id)
        self._pass(
            "422 emitted for invalid timestamp with X-Request-ID echoed",
            "ok",
            expected_payload={"invalid_timestamp_status": 422, "x-request-id": request_id},
            received_payload={"invalid_timestamp_status": status, "x-request-id": headers.get("x-request-id")},
        )

    def test_request_log_line_contains_required_keys(self):
        self._info("Checks request log format always includes stable request keys.")
        middleware = RequestLoggingMiddleware(app=lambda scope, receive, send: None)

        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "path": "/health",
            "raw_path": b"/health",
            "scheme": "http",
            "query_string": b"",
            "headers": [],
            "client": ("testclient", 1234),
            "server": ("testserver", 80),
        }
        request = StarletteRequest(scope)

        async def call_next(_request):
            return PlainTextResponse("ok", status_code=200)

        with patch("app.middleware.request_logging.logger.info") as mocked_info:
            response = asyncio.run(middleware.dispatch(request, call_next))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(mocked_info.called)
        format_string = mocked_info.call_args[0][0]
        self.assertIn("request_id=", format_string)
        self.assertIn("method=", format_string)
        self.assertIn("path=", format_string)
        self.assertIn("status_code=", format_string)
        self.assertIn("duration_ms=", format_string)
        self._pass(
            "request log line contains request_id/method/path/status_code/duration_ms keys",
            "ok",
            expected_payload={
                "contains": ["request_id=", "method=", "path=", "status_code=", "duration_ms="],
            },
            received_payload={"format_string": format_string},
        )

    def test_request_id_header_present_on_500_in_middleware(self):
        self._info("Checks middleware returns 500 response with X-Request-ID when downstream raises.")
        middleware = RequestLoggingMiddleware(app=lambda scope, receive, send: None)
        request_id = str(uuid4())
        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "path": "/boom",
            "raw_path": b"/boom",
            "scheme": "http",
            "query_string": b"",
            "headers": [(b"x-request-id", request_id.encode())],
            "client": ("testclient", 1234),
            "server": ("testserver", 80),
        }
        request = StarletteRequest(scope)

        async def call_next(_request):
            raise RuntimeError("boom")

        response = asyncio.run(middleware.dispatch(request, call_next))
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.headers.get("x-request-id"), request_id)
        self._pass(
            "500 middleware fallback includes X-Request-ID",
            "ok",
            expected_payload={"status": 500, "x-request-id": request_id},
            received_payload={"status": response.status_code, "x-request-id": response.headers.get("x-request-id")},
        )
