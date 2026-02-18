from __future__ import annotations

from tests.base import BackendTestBase


class AuthTests(BackendTestBase):
    def test_auth_signup_login_me(self):
        self._info("Checks signup/login/me flow and auth protection on /v1/auth/me.")
        status_missing, _ = self._request("GET", "/v1/auth/me", include_tz=False)
        self.assertEqual(status_missing, 401)

        email, password, token = self._signup()
        self.assertTrue(token)

        status_login, body_login = self._request(
            "POST",
            "/v1/auth/login",
            payload={"email": email, "password": password},
            include_tz=False,
        )
        self.assertEqual(status_login, 200, body_login)
        self.assertIn("access_token", body_login)

        me = self._me(token)
        self.assertEqual(me["email"], email.lower())
        self.assertIn("user_id", me)
        self._pass(
            "signup/login/me all valid",
            {"login_status": status_login, "me_email": me["email"]},
            expected_payload={"access_token": "<jwt>", "me": {"user_id": "<int>", "email": email.lower()}},
            received_payload={"login": body_login, "me": me},
        )
