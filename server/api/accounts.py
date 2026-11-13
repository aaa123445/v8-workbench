"""Account HTTP routes. Browser credentials stay in an HttpOnly cookie."""

from __future__ import annotations

from typing import Literal
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from ..core.accounts import SESSION_TTL, AccountError
from ..core.auth import ROLE_RANK, AuthError, Principal
from ..core.container import get_container

COOKIE = "v8wb_session"


def same_origin(request: Request):
    """Protect cookie mutations, including login CSRF; bearer APIs remain independent."""
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    origin = request.headers.get("origin")
    if origin:
        parsed = urlsplit(origin)
        if (
            parsed.scheme != request.url.scheme
            or parsed.netloc.lower() != request.url.netloc.lower()
        ):
            raise HTTPException(403, detail={"message": "请从工作台页面发起此操作"})
    elif request.headers.get("x-requested-with") != "V8Workbench":
        raise HTTPException(
            403, detail={"message": "请求缺少同源校验，请刷新页面后重试"}
        )
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, detail={"message": "不允许跨站操作"})


def session_user(request: Request):
    same_origin(request)
    return get_container().accounts.session_user(request.cookies.get(COOKIE, ""))


def active_user(user=Depends(session_user)):
    get_container().accounts.require_approved(user)
    return user


class LoginReq(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=128)


class RegisterReq(LoginReq):
    display_name: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=10, max_length=128)


class PasswordReq(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


class PersonalKeyReq(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    role: Literal["reader", "writer", "admin"] = "reader"


class ReviewReq(BaseModel):
    status: Literal["approved", "rejected", "disabled"]
    role: Literal["reader", "writer", "admin"] = "reader"
    note: str = Field(default="", max_length=500)


def register_routes(app, principal, need):
    @app.exception_handler(AccountError)
    async def account_error(_, exc):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=exc.status,
            content={"error": "account_error", "message": str(exc)},
        )

    @app.exception_handler(AuthError)
    async def key_error(_, exc):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=400,
            content={"error": "invalid_key_request", "message": str(exc)},
        )

    @app.post(
        "/api/v1/auth/register", status_code=201, dependencies=[Depends(same_origin)]
    )
    def register(req: RegisterReq, request: Request):
        c = get_container()
        c.accounts.throttle(
            "register", request.client.host if request.client else "unknown", 5
        )
        user = c.accounts.register(req.username, req.display_name, req.password)
        return {
            "user": user,
            "message": "注册成功，请登录查看审批状态，获批后即可使用工作台",
        }

    @app.post("/api/v1/auth/login", dependencies=[Depends(same_origin)])
    def login(req: LoginReq, request: Request, response: Response):
        c = get_container()
        c.accounts.throttle(
            "login-ip", request.client.host if request.client else "unknown", 30
        )
        c.accounts.throttle("login-user", req.username.strip().lower(), 15)
        raw, user = c.accounts.login(req.username, req.password)
        response.set_cookie(
            COOKIE,
            raw,
            max_age=SESSION_TTL,
            httponly=True,
            secure=request.url.scheme == "https",
            samesite="lax",
            path="/",
        )
        return {"user": user}

    @app.get("/api/v1/auth/me")
    def me(user=Depends(session_user)):
        return {"user": user}

    @app.post("/api/v1/auth/logout", dependencies=[Depends(same_origin)])
    def logout(request: Request, response: Response):
        get_container().accounts.logout(request.cookies.get(COOKIE, ""))
        response.delete_cookie(
            COOKIE,
            path="/",
            httponly=True,
            secure=request.url.scheme == "https",
            samesite="lax",
        )
        return {"ok": True}

    @app.post("/api/v1/auth/password")
    def change_password(
        req: PasswordReq,
        response: Response,
        request: Request,
        user=Depends(session_user),
    ):
        c = get_container()
        c.accounts.throttle("password", user["id"], 10)
        c.accounts.change_password(user["id"], req.current_password, req.new_password)
        response.delete_cookie(
            COOKIE,
            path="/",
            httponly=True,
            secure=request.url.scheme == "https",
            samesite="lax",
        )
        return {
            "message": "密码已修改，所有浏览器会话已退出，请重新登录；API Key 可在个人页面单独吊销"
        }

    @app.get("/api/v1/account/keys")
    def my_keys(user=Depends(active_user)):
        return {"keys": get_container().auth.list_keys(owner_user_id=user["id"])}

    @app.post("/api/v1/account/keys", status_code=201)
    def create_my_key(req: PersonalKeyReq, user=Depends(active_user)):
        if not req.name.strip():
            raise AccountError("请填写 Key 名称")
        if ROLE_RANK[req.role] > ROLE_RANK[user["role"]]:
            raise AccountError("Key 权限不能超过账号权限", 403)
        raw, meta = get_container().auth.create_key(
            req.name.strip(), req.role, owner_user_id=user["id"]
        )
        return {"key": raw, "warning": "只显示一次，请立即保存", **meta}

    @app.delete("/api/v1/account/keys/{prefix}")
    def revoke_my_key(prefix: str, user=Depends(active_user)):
        if not get_container().auth.revoke(prefix, owner_user_id=user["id"]):
            raise AccountError("Key 不存在或已吊销", 404)
        return {"revoked": True}

    @app.get("/api/v1/admin/users")
    def users(p: Principal = Depends(principal)):
        need(p, "admin")
        return {"users": get_container().accounts.list_users()}

    @app.patch("/api/v1/admin/users/{user_id}")
    def review_user(user_id: str, req: ReviewReq, p: Principal = Depends(principal)):
        need(p, "admin")
        return {
            "user": get_container().accounts.review(
                user_id, req.status, req.role, req.note, p
            )
        }
