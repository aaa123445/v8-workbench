"""HTTP API。

/health 和 /openapi.json 免鉴权，其余需要 Bearer Key。
所有业务错误统一 envelope，便于 CLI 和 agent 解析。
"""

from __future__ import annotations

from typing import Any

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

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
    title="V8 客开工作台",
    version="0.1.0",
    description="致远 V8 客开知识检索、开发规范编排与知识沉淀服务",
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
    if not c.settings.require_auth and not raw:
        return Principal("anon", "anonymous", "admin", 10**6, 10**9)
    try:
        p = c.auth.authenticate(raw)
        c.auth.check_quota(p)
        return p
    except AuthError as e:
        raise HTTPException(status_code=401, detail={"error": "unauthorized", "message": str(e)}) from e
    except QuotaExceeded as e:
        raise HTTPException(
            status_code=429,
            detail={"error": "quota_exceeded", "message": str(e), "retry_after": e.retry_after},
        ) from e


def _need(p: Principal, role: str) -> None:
    if not p.can(role):
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "message": f"需要 {role} 权限，当前 {p.role}"},
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


class ReadReq(BaseModel):
    id: str = ""
    title: str = ""
    offset: int = Field(default=0, ge=0)
    max_chars: int | None = None


class RulesReq(BaseModel):
    task: str = ""
    include_docs: bool = False
    per_doc_chars: int = Field(default=6000, ge=500, le=60000)


class SubmitReq(BaseModel):
    title: str
    content: str
    path: str = ""
    tags: list[str] = Field(default_factory=list)
    summary: str = ""
    url: str = ""
    project: str = ""
    version_hint: str = ""
    source: str = "agent"


class CreateKeyReq(BaseModel):
    name: str
    role: str = "reader"
    rpm: int | None = None
    daily: int | None = None


# ---------------- 路由 ----------------

@app.get("/health")
async def health() -> dict[str, Any]:
    return _svc().health()


@app.get("/api/v1/stats")
async def stats(p: Principal = Depends(principal)) -> dict[str, Any]:
    return _svc().stats()


@app.post("/api/v1/search")
async def search(req: SearchReq, p: Principal = Depends(principal)) -> dict[str, Any]:
    c = get_container()
    out = _svc().search(
        req.query, limit=req.limit, domain=req.domain, source=req.source, tag=req.tag
    )
    c.auth.log_usage(p, "search", True, req.query[:120])
    return out


@app.post("/api/v1/read")
async def read(req: ReadReq, p: Principal = Depends(principal)) -> dict[str, Any]:
    c = get_container()
    try:
        return _svc().read(req.id, title=req.title, max_chars=req.max_chars, offset=req.offset)
    finally:
        c.auth.log_usage(p, "read", True, (req.id or req.title)[:120])


@app.get("/api/v1/domains")
async def domains(p: Principal = Depends(principal)) -> dict[str, Any]:
    return _svc().domains()


@app.post("/api/v1/rules")
async def rules(req: RulesReq, p: Principal = Depends(principal)) -> dict[str, Any]:
    c = get_container()
    out = _svc().rules(req.task, include_docs=req.include_docs, per_doc_chars=req.per_doc_chars)
    c.auth.log_usage(p, "rules", True, req.task[:120])
    return out


@app.get("/api/v1/recent")
async def recent(limit: int = 20, p: Principal = Depends(principal)) -> dict[str, Any]:
    return _svc().recent(limit)


# ---------------- 知识写入 ----------------

@app.post("/api/v1/knowledge")
async def submit(req: SubmitReq, p: Principal = Depends(principal)) -> dict[str, Any]:
    _need(p, "writer")
    c = get_container()
    out = _svc().submit_knowledge(
        title=req.title,
        content=req.content,
        actor=p.key_prefix,
        source=req.source,
        path=req.path,
        tags=req.tags,
        summary=req.summary,
        url=req.url,
        project=req.project,
        version_hint=req.version_hint,
    )
    c.auth.log_usage(p, "submit", True, req.title[:120])
    return out


@app.post("/api/v1/knowledge/batch")
async def submit_batch(items: list[SubmitReq], p: Principal = Depends(principal)) -> dict[str, Any]:
    _need(p, "writer")
    svc = _svc()
    ok, failed = [], []
    for it in items:
        try:
            ok.append(
                svc.submit_knowledge(
                    title=it.title, content=it.content, actor=p.key_prefix, source=it.source,
                    path=it.path, tags=it.tags, summary=it.summary, url=it.url,
                    project=it.project, version_hint=it.version_hint,
                )
            )
        except Exception as e:  # noqa: BLE001
            failed.append({"title": it.title, "error": str(e)})
    return {"count": len(ok), "results": ok, "failed": failed}


@app.delete("/api/v1/knowledge/{doc_id}")
async def delete_doc(doc_id: str, p: Principal = Depends(principal)) -> dict[str, Any]:
    _need(p, "admin")
    return _svc().delete_doc(doc_id, p.key_prefix)


# ---------------- 管理员 ----------------

@app.post("/api/v1/admin/keys")
async def create_key(req: CreateKeyReq, p: Principal = Depends(principal)) -> dict[str, Any]:
    _need(p, "admin")
    raw, meta = get_container().auth.create_key(req.name, req.role, rpm=req.rpm, daily=req.daily)
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
    force: bool = False,
    limit: int | None = None,
    p: Principal = Depends(principal),
) -> dict[str, Any]:
    _need(p, "admin")
    from ..core.yuque import sync_book

    c = get_container()
    if not c.settings.yuque_book:
        raise HTTPException(status_code=400, detail={"error": "no_book", "message": "未配置语雀知识库"})
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
        raise HTTPException(status_code=502, detail={"error": "sync_failed", "message": str(e)}) from e
    c.rebuild_index()
    return stat


@app.post("/api/v1/admin/rebuild")
async def rebuild(refresh_meta: bool = False, p: Principal = Depends(principal)) -> dict[str, Any]:
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


# ---------------- 前端 ----------------
# 放在最后注册，避免 / 和 /static 抢在 /api 前面匹配。

_WEB_DIR = Path(__file__).resolve().parents[2] / "web"

if (_WEB_DIR / "index.html").exists():
    app.mount("/static", StaticFiles(directory=str(_WEB_DIR)), name="static")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(str(_WEB_DIR / "index.html"))
