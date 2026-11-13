"""HTTP API。

业务接口支持已批准账号的浏览器会话或 Bearer Key。
注册、登录、健康检查与静态页面公开，其余接口校验身份与角色。
所有业务错误统一 envelope，便于 CLI 和 agent 解析。
"""

from __future__ import annotations

from typing import Any, Literal

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .accounts import COOKIE, same_origin, register_routes
from .knowledge import register_knowledge, Proposal
from .call_logging import CallLoggingMiddleware
from .call_history import register_call_history
from ..core.auth import AuthError, Principal, QuotaExceeded
from ..core.container import get_container
from ..core.service import ServiceError, WorkbenchService


@asynccontextmanager
async def lifespan(_: FastAPI):
    from . import scheduler

    c = get_container()
    scheduler.start_background(c)
    yield


app = FastAPI(
    title="TeamKB 团队知识库",
    version="0.5.0",
    description="团队知识分类、检索、贡献审核与 Agent 经验沉淀",
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _svc() -> WorkbenchService:
    return WorkbenchService(get_container())


def _bearer(authorization: str | None) -> str:
    if not authorization:
        return ""
    parts = authorization.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return authorization.strip()


async def principal(
    request: Request,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> Principal:
    c = get_container()
    raw = _bearer(authorization) or (x_api_key or "")
    cookie = request.cookies.get(COOKIE, "")
    if not c.settings.require_auth and not raw and not cookie:
        return Principal("anon", "anonymous", "admin", 10**6, 10**9)
    try:
        if raw:
            p = c.auth.authenticate(raw)
        else:
            same_origin(request)
            p = c.accounts.principal(cookie)
        request.state.call_principal = p
        c.auth.check_quota(p)
        return p
    except AuthError as e:
        raise HTTPException(
            status_code=401, detail={"error": "unauthorized", "message": str(e)}
        ) from e
    except QuotaExceeded as e:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "quota_exceeded",
                "message": str(e),
                "retry_after": e.retry_after,
            },
        ) from e


def _need(p: Principal, role: str) -> None:
    if not p.can(role):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "forbidden",
                "message": f"需要 {role} 权限，当前 {p.role}",
            },
        )


@app.exception_handler(ServiceError)
async def _svc_err(_: Request, exc: ServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"error": exc.code, "message": exc.message, "hint": exc.hint},
    )


# ---------------- 模型 ----------------


class SearchReq(BaseModel):
    query: str
    limit: int = Field(default=8, ge=1, le=50)
    domain: str = ""
    source: str = ""
    tag: str = ""
    category_id: str = ""


class ReadReq(BaseModel):
    id: str = ""
    title: str = ""
    offset: int = Field(default=0, ge=0)
    max_chars: int | None = None


class RulesReq(BaseModel):
    task: str = ""
    include_docs: bool = False
    per_doc_chars: int = Field(default=6000, ge=500, le=60000)


class SubmitReq(Proposal):
    content: str = Field(max_length=200000)
    # Legacy clients may submit unstructured content; still requires review.
    source: Literal["agent", "manual", "upload"] = "manual"
    path: str = ""
    project: str = ""


class CreateKeyReq(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    role: Literal["reader", "writer", "admin"] = "reader"
    rpm: int | None = Field(default=None, ge=1, le=10000)
    daily: int | None = Field(default=None, ge=1, le=1000000000)


# ---------------- 路由 ----------------


@app.get("/health")
async def health() -> dict[str, Any]:
    return _svc().health()


@app.get("/api/v1/stats")
async def stats(p: Principal = Depends(principal)) -> dict[str, Any]:
    return _svc().stats()


@app.post("/api/v1/search")
async def search(req: SearchReq, p: Principal = Depends(principal)) -> dict[str, Any]:
    out = _svc().search(
        req.query,
        limit=req.limit,
        domain=req.domain,
        source=req.source,
        tag=req.tag,
        category_id=req.category_id,
    )
    return out


@app.post("/api/v1/read")
async def read(req: ReadReq, p: Principal = Depends(principal)) -> dict[str, Any]:
    return _svc().read(
        req.id, title=req.title, max_chars=req.max_chars, offset=req.offset
    )


@app.get("/api/v1/domains")
async def domains(p: Principal = Depends(principal)) -> dict[str, Any]:
    return _svc().domains()


@app.post("/api/v1/rules")
async def rules(req: RulesReq, p: Principal = Depends(principal)) -> dict[str, Any]:
    out = _svc().rules(
        req.task, include_docs=req.include_docs, per_doc_chars=req.per_doc_chars
    )
    return out


@app.get("/api/v1/recent")
async def recent(limit: int = 20, p: Principal = Depends(principal)) -> dict[str, Any]:
    return _svc().recent(limit)


# ---------------- 知识写入 ----------------


@app.post("/api/v1/knowledge")
async def submit(req: SubmitReq, p: Principal = Depends(principal)) -> dict[str, Any]:
    _need(p, "writer")
    payload = req.model_dump()
    # Old agents lack verification fields: keep their content as review candidates.
    payload["source"] = "manual" if payload["source"] == "agent" else payload["source"]
    return get_container().knowledge.propose(p, payload)


@app.post("/api/v1/knowledge/batch")
async def submit_batch(
    items: list[SubmitReq], request: Request, p: Principal = Depends(principal)
) -> dict[str, Any]:
    _need(p, "writer")
    ok, failed = [], []
    for it in items:
        try:
            payload = it.model_dump()
            payload["source"] = (
                "manual" if payload["source"] == "agent" else payload["source"]
            )
            ok.append(get_container().knowledge.propose(p, payload))
        except Exception as e:
            failed.append({"title": it.title, "error": str(e)})
    request.state.call_outcome = (
        "partial" if failed and ok else "failed" if failed else "success"
    )
    return {"count": len(ok), "results": ok, "failed": failed}


@app.delete("/api/v1/knowledge/{doc_id}")
async def delete_doc(doc_id: str, p: Principal = Depends(principal)) -> dict[str, Any]:
    _need(p, "admin")
    return _svc().delete_doc(doc_id, p.key_prefix)


# ---------------- 管理员 ----------------


@app.post("/api/v1/admin/keys")
async def create_key(
    req: CreateKeyReq, p: Principal = Depends(principal)
) -> dict[str, Any]:
    _need(p, "admin")
    raw, meta = get_container().auth.create_key(
        req.name, req.role, rpm=req.rpm, daily=req.daily, owner_user_id=p.user_id
    )
    return {
        "key": raw,
        "warning": "此 key 只显示一次，请立即保存",
        **meta,
    }


@app.get("/api/v1/admin/keys")
async def list_keys(p: Principal = Depends(principal)) -> dict[str, Any]:
    _need(p, "admin")
    return {"keys": get_container().auth.list_keys()}


@app.delete("/api/v1/admin/keys/{prefix}")
async def revoke_key(prefix: str, p: Principal = Depends(principal)) -> dict[str, Any]:
    _need(p, "admin")
    return {"revoked": get_container().auth.revoke(prefix)}


@app.get("/api/v1/admin/usage")
async def usage(days: int = 7, p: Principal = Depends(principal)) -> dict[str, Any]:
    _need(p, "admin")
    return {"usage": get_container().auth.usage_summary(days)}


@app.post("/api/v1/admin/sync/yuque")
async def sync_yuque(
    request: Request,
    force: bool = False,
    limit: int | None = None,
    p: Principal = Depends(principal),
) -> dict[str, Any]:
    _need(p, "admin")
    from ..core.yuque import sync_book

    c = get_container()
    if not c.settings.yuque_book:
        raise HTTPException(
            status_code=400, detail={"error": "no_book", "message": "未配置语雀知识库"}
        )
    try:
        stat = sync_book(
            c.repo,
            c.settings.yuque_book,
            token=c.settings.yuque_token,
            force=force,
            actor=p.key_prefix,
            limit=limit,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=502, detail={"error": "sync_failed", "message": str(e)}
        ) from e
    c.rebuild_index()
    request.state.call_outcome = (
        "partial"
        if stat.get("failed") and stat.get("fetched")
        else "failed"
        if stat.get("failed")
        else "success"
    )
    return stat


@app.post("/api/v1/admin/rebuild")
async def rebuild(
    refresh_meta: bool = False, p: Principal = Depends(principal)
) -> dict[str, Any]:
    """重建索引。

    refresh_meta=true 时同时重算派生元数据（知识域/版本/标签/摘要）。
    元数据推断规则改进后，老数据需要这样刷一次。
    """
    _need(p, "admin")
    c = get_container()
    out: dict[str, Any] = {}
    if refresh_meta:
        out["meta"] = c.repo.refresh_derived()
    out["indexed"] = c.rebuild_index()
    return out


register_knowledge(app, principal, _need, get_container=lambda: get_container())
register_routes(app, principal, _need)
register_call_history(app, get_container=lambda: get_container())


@app.middleware("http")
async def private_api_responses(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Vary"] = ", ".join(
            filter(None, [response.headers.get("Vary", ""), "Cookie", "Authorization"])
        )
    return response


app.add_middleware(CallLoggingMiddleware, get_container=lambda: get_container())

# ---------------- 前端 ----------------
# 放在最后注册，避免 / 和 /static 抢在 /api 前面匹配。

_WEB_DIR = Path(__file__).resolve().parents[2] / "web" / "dist"

if (_WEB_DIR / "index.html").exists():
    app.mount("/static", StaticFiles(directory=str(_WEB_DIR)), name="static")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(str(_WEB_DIR / "index.html"))
