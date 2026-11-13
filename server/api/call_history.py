"""Personal log reads do not consume quota or recursively generate logs."""

from __future__ import annotations

from typing import Literal
from fastapi import HTTPException, Query, Request
from ..core.accounts import AccountError
from ..core.auth import AuthError
from .accounts import COOKIE


def register_call_history(app, get_container):
    def viewer(request: Request):
        c = get_container()
        authorization = request.headers.get("authorization", "")
        parts = authorization.split(None, 1)
        raw = (
            parts[1]
            if len(parts) == 2 and parts[0].lower() == "bearer"
            else authorization
        )
        raw = raw or request.headers.get("x-api-key", "")
        if raw:
            try:
                return c.auth.authenticate(raw)
            except AuthError as exc:
                raise AccountError(str(exc), 401) from exc
        return c.accounts.principal(request.cookies.get(COOKIE, ""))

    @app.get("/api/v1/account/calls")
    def history(
        request: Request,
        page: int = Query(default=1, ge=1, le=100000),
        page_size: int = Query(default=20, ge=1, le=100),
        operation: Literal[
            "",
            "search",
            "read",
            "rules",
            "domains",
            "stats",
            "recent",
            "submit",
            "submit_batch",
            "delete",
            "sync",
            "rebuild",
            "propose",
            "review",
            "rollback",
            "categories",
            "library",
            "standards",
        ] = "",
        client: Literal["", "web", "mcp", "cli", "api"] = "",
        outcome: Literal["", "success", "partial", "failed"] = "",
        key_prefix: str = Query(default="", max_length=80),
        query: str = Query(default="", max_length=120),
        since: int | None = Query(default=None, ge=0, le=4102444800),
        until: int | None = Query(default=None, ge=0, le=4102444800),
    ):
        p = viewer(request)
        if since is not None and until is not None and since >= until:
            raise AccountError("开始时间需要早于结束时间")
        return get_container().calls.list(
            p,
            page=page,
            page_size=page_size,
            operation=operation,
            client=client,
            outcome=outcome,
            key_prefix=key_prefix,
            query=query.strip(),
            since=since,
            until=until,
        )

    @app.get("/api/v1/account/calls/{log_id}")
    def detail(log_id: int, request: Request):
        p = viewer(request)
        result = get_container().calls.get(p, log_id)
        if not result:
            raise HTTPException(404, detail={"message": "调用记录不存在或已过期"})
        return result
