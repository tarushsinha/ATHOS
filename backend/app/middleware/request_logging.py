from __future__ import annotations

import logging
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse

logger = logging.getLogger("athos.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            response = PlainTextResponse("Internal Server Error", status_code=500)
            response.headers["X-Request-ID"] = request_id
            duration_ms = (time.perf_counter() - started) * 1000.0
            logger.info(
                "request_complete request_id=%s method=%s path=%s status_code=%s duration_ms=%.2f user_id=%s",
                request_id,
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
                getattr(request.state, "user_id", None),
            )
            return response

        response.headers["X-Request-ID"] = request_id
        duration_ms = (time.perf_counter() - started) * 1000.0
        logger.info(
            "request_complete request_id=%s method=%s path=%s status_code=%s duration_ms=%.2f user_id=%s",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            getattr(request.state, "user_id", None),
        )
        return response
