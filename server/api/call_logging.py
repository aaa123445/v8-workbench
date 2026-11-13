"""ASGI capture: bounded, redacted snapshots without consuming responses twice."""

from __future__ import annotations
import logging
import time
from urllib.parse import parse_qs

from ..core.call_logs import (
    REQUEST_LIMIT,
    RESPONSE_LIMIT,
    REQUEST_CAPTURE_LIMIT,
    RESPONSE_CAPTURE_LIMIT,
    operation_for,
    outcome_for,
    snapshot,
)

logger = logging.getLogger(__name__)


class CallLoggingMiddleware:
    def __init__(self, app, get_container):
        self.app, self.get_container = app, get_container

    async def __call__(self, scope, receive, send):
        operation = (
            operation_for(scope.get("method", ""), scope.get("path", ""))
            if scope["type"] == "http"
            else None
        )
        if not operation:
            return await self.app(scope, receive, send)
        started = time.perf_counter()
        started_at = time.time()
        request_body, response_body = bytearray(), bytearray()
        request_size, response_size, status, completed = 0, 0, 500, False
        response_started = False
        state = scope.setdefault("state", {})

        async def capture_receive():
            nonlocal request_size
            message = await receive()
            if message["type"] == "http.request":
                body = message.get("body", b"")
                request_size += len(body)
                request_body.extend(
                    body[: max(0, REQUEST_CAPTURE_LIMIT - len(request_body))]
                )
            return message

        async def capture_send(message):
            nonlocal status, response_size, completed, response_started
            if message["type"] == "http.response.start":
                status = message["status"]
            if message["type"] == "http.response.body":
                body = message.get("body", b"")
                response_size += len(body)
                response_body.extend(
                    body[: max(0, RESPONSE_CAPTURE_LIMIT - len(response_body))]
                )
            await send(message)
            if message["type"] == "http.response.start":
                response_started = True
            if message["type"] == "http.response.body" and not message.get(
                "more_body", False
            ):
                completed = True

        try:
            await self.app(scope, capture_receive, capture_send)
        finally:
            principal = state.get("call_principal")
            if principal and principal.key_prefix != "anon":
                request_data = None
                actual_outcome = "success" if completed and status < 400 else "failed"
                try:
                    request_data, request_truncated = snapshot(
                        bytes(request_body), request_size, REQUEST_LIMIT
                    )
                    response_data, response_truncated = snapshot(
                        bytes(response_body), response_size, RESPONSE_LIMIT
                    )
                    if not completed:
                        if not response_started:
                            status = 500
                        response_data = {
                            "error": "internal_error",
                            "message": "服务器内部错误或调用中断",
                        }
                    query = parse_qs(
                        scope.get("query_string", b"").decode(errors="replace")
                    )
                    safe_query = {
                        k: v[-1]
                        for k, v in query.items()
                        if k in {"limit", "force", "refresh_meta"}
                    }
                    if safe_query:
                        request_data = {"body": request_data, "query": safe_query}
                    headers = dict(scope.get("headers", []))
                    client = (
                        headers.get(b"x-v8wb-client", b"")
                        .decode(errors="replace")
                        .lower()
                    )
                    if client not in {"web", "mcp", "cli"}:
                        client = "web" if principal.kind == "session" else "api"
                    actual_outcome = (
                        "failed"
                        if not completed
                        else state.get("call_outcome")
                        or outcome_for(status, response_data)
                    )
                    c = self.get_container()
                    c.calls.record(
                        principal,
                        operation=operation,
                        method=scope["method"],
                        path=scope["path"],
                        client=client,
                        status=status,
                        duration_ms=(time.perf_counter() - started) * 1000,
                        request_data=request_data,
                        response_data=response_data,
                        request_truncated=request_truncated,
                        response_truncated=response_truncated,
                        outcome=actual_outcome,
                        ts=started_at,
                    )
                except Exception:
                    logger.error(
                        "Unable to persist call history (%s %s)",
                        scope["method"],
                        operation,
                    )
                try:
                    self.get_container().auth.log_usage(
                        principal,
                        operation,
                        actual_outcome == "success",
                        str(request_data or "")[:120],
                    )
                except Exception:
                    # A log-write failure must never change the business response or
                    # expose payloads/credentials in the server's diagnostic output.
                    logger.error(
                        "Unable to persist call log (%s %s)", scope["method"], operation
                    )
