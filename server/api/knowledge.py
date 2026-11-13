"""Reviewed team knowledge API shared by browsers, CLI and MCP."""

from typing import Literal

from fastapi import Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..core.knowledge import KnowledgeError, actor_id


class Proposal(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=20, max_length=200000)
    category_id: str = Field(default="uncategorized", max_length=100)
    tags: list[str] = Field(default_factory=list, max_length=30)
    summary: str = Field(default="", max_length=2000)
    source: Literal["manual", "agent", "upload"] = "manual"
    target_doc_id: str = Field(default="", max_length=200)
    base_version: int | None = Field(default=None, ge=1)
    problem: str = Field(default="", max_length=10000)
    solution: str = Field(default="", max_length=20000)
    verification: str = Field(default="", max_length=10000)
    limitations: str = Field(default="", max_length=10000)
    verified: bool = False
    reusable: bool = False
    version_hint: str = Field(default="", max_length=200)
    url: str = Field(default="", max_length=2000)


class Category(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    parent_id: str | None = Field(default=None, max_length=100)


class Review(BaseModel):
    action: Literal["publish", "changes_requested", "reject"]
    note: str = Field(default="", max_length=4000)


class Rollback(BaseModel):
    version: int = Field(ge=1)
    expected_version: int = Field(ge=1)


class Standard(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category_id: str = "standards"
    description: str = Field(default="", max_length=10000)
    checklist: list[str] = Field(default_factory=list, max_length=100)
    doc_ids: list[str] = Field(default_factory=list, max_length=50)


class Policy(BaseModel):
    auto_publish: bool


def register_knowledge(app, principal, need, get_container):
    def svc():
        return get_container().knowledge

    @app.exception_handler(KnowledgeError)
    async def knowledge_error(_: Request, exc: KnowledgeError):
        return JSONResponse(
            status_code=exc.status,
            content={"error": "knowledge_error", "message": str(exc)},
        )

    @app.get("/api/v1/categories")
    def categories(p=Depends(principal)):
        return {"categories": svc().categories()}

    @app.post("/api/v1/categories")
    def add_category(req: Category, p=Depends(principal)):
        need(p, "admin")
        return svc().save_category(**req.model_dump())

    @app.put("/api/v1/categories/{cid}")
    def edit_category(cid: str, req: Category, p=Depends(principal)):
        need(p, "admin")
        return svc().save_category(**req.model_dump(), cid=cid)

    @app.delete("/api/v1/categories/{cid}")
    def delete_category(cid: str, p=Depends(principal)):
        need(p, "admin")
        return svc().delete_category(cid)

    @app.get("/api/v1/library")
    def library(
        category_id: str = "",
        query: str = Query("", max_length=300),
        tag: str = "",
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        sort: Literal["updated", "oldest", "title"] = "updated",
        p=Depends(principal),
    ):
        return svc().browse(category_id, query, tag, page, page_size, sort)

    @app.post("/api/v1/contributions")
    def propose(req: Proposal, submit: bool = True, p=Depends(principal)):
        need(p, "writer")
        return svc().propose(p, req.model_dump(), submit)

    @app.put("/api/v1/contributions/{cid}")
    def edit_proposal(
        cid: str, req: Proposal, submit: bool = False, p=Depends(principal)
    ):
        need(p, "writer")
        return svc().propose(p, req.model_dump(), submit, cid)

    @app.get("/api/v1/contributions")
    def proposals(
        status: str = "",
        review: bool = False,
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        p=Depends(principal),
    ):
        return svc().contributions(p, status, page, page_size, review)

    @app.get("/api/v1/contributions/{cid}")
    def proposal(cid: str, p=Depends(principal)):
        return svc().contribution(p, cid)

    @app.post("/api/v1/contributions/{cid}/review")
    def review(cid: str, req: Review, p=Depends(principal)):
        need(p, "admin")
        return svc().review(p, cid, req.action, req.note)

    @app.get("/api/v1/versions/{doc_id}")
    def versions(doc_id: str, p=Depends(principal)):
        return {"versions": svc().versions(doc_id)}

    @app.get("/api/v1/versions/{doc_id}/{number}")
    def version(doc_id: str, number: int, p=Depends(principal)):
        return svc().version(doc_id, number)

    @app.post("/api/v1/versions/{doc_id}/rollback")
    def rollback(doc_id: str, req: Rollback, p=Depends(principal)):
        need(p, "admin")
        return svc().rollback(p, doc_id, req.version, req.expected_version)

    @app.get("/api/v1/standards")
    def standards(category_id: str = "", p=Depends(principal)):
        return {"standards": svc().standards(category_id)}

    @app.post("/api/v1/standards")
    def add_standard(req: Standard, p=Depends(principal)):
        need(p, "admin")
        return svc().save_standard(p, req.model_dump())

    @app.put("/api/v1/standards/{rid}")
    def edit_standard(rid: str, req: Standard, p=Depends(principal)):
        need(p, "admin")
        return svc().save_standard(p, req.model_dump(), rid)

    @app.delete("/api/v1/standards/{rid}")
    def delete_standard(rid: str, p=Depends(principal)):
        need(p, "admin")
        with get_container().db.write() as conn:
            deleted = conn.execute("DELETE FROM rule_sets WHERE id=?", (rid,)).rowcount
            conn.execute(
                "INSERT INTO knowledge_audit(actor,action,target,details,created_at) VALUES (?,?,?,?,?)",
                (actor_id(p), "standard_delete", rid, "{}", __import__("time").time()),
            )
        return {"deleted": bool(deleted)}

    @app.put("/api/v1/admin/keys/{prefix}/policy")
    def key_policy(prefix: str, req: Policy, p=Depends(principal)):
        need(p, "admin")
        c = get_container()
        with c.db.write() as conn:
            row = conn.execute(
                "SELECT role FROM api_keys WHERE key_prefix=? AND enabled=1", (prefix,)
            ).fetchone()
            if not row:
                raise KnowledgeError("Key 不存在或已禁用", 404)
            if req.auto_publish and row["role"] == "reader":
                raise KnowledgeError("只读 Key 不能自动发布")
            conn.execute(
                "UPDATE api_keys SET auto_publish=? WHERE key_prefix=?",
                (int(req.auto_publish), prefix),
            )
            conn.execute(
                "INSERT INTO knowledge_audit(actor,action,target,details,created_at) VALUES (?,?,?,?,?)",
                (
                    actor_id(p),
                    "key_policy",
                    prefix,
                    __import__("json").dumps(req.model_dump()),
                    __import__("time").time(),
                ),
            )
        return {"prefix": prefix, "auto_publish": req.auto_publish}
