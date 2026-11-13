"""Knowledge relationships and read-only cloud Q&A, using existing account permissions."""

from typing import Literal

from fastapi import Depends, Query
from pydantic import BaseModel, Field

from ..core.graph import GraphService


class Link(BaseModel):
    source_id: str = Field(min_length=1, max_length=200)
    target_id: str = Field(min_length=1, max_length=200)
    kind: Literal["related", "prerequisite", "solution", "example", "contrast"] = (
        "related"
    )
    note: str = Field(default="", max_length=1000)


class Classification(BaseModel):
    title: str = Field(default="", max_length=300)
    content: str = Field(default="", max_length=10000)


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class Question(BaseModel):
    question: str = Field(min_length=2, max_length=1200)
    category_id: str = Field(default="", max_length=100)
    scenario: Literal[
        "auto", "explore", "troubleshoot", "develop", "compare", "learn"
    ] = "auto"
    mode: Literal["auto", "search", "chain"] = "auto"
    history: list[ConversationTurn] = Field(default_factory=list, max_length=12)


class AgentSettings(BaseModel):
    enabled: bool = False
    base_url: str = Field(default="", max_length=1000)
    model: str = Field(default="", max_length=150)
    api_key: str = Field(default="", max_length=1000)
    clear_key: bool = False


def register_graph(app, principal, need, get_container):
    # Single assistant instance per container, including concurrency guard.
    def agent():
        return get_container().assistant

    @app.get("/api/v1/graph/all")
    def all_graph(category_id: str = "", p=Depends(principal)):
        return GraphService(get_container()).all_graph(category_id)

    @app.get("/api/v1/graph")
    def graph(
        doc_id: str = Query(..., max_length=200),
        category_id: str = "",
        depth: int = Query(1, ge=1, le=2),
        scenario: Literal[
            "explore", "troubleshoot", "develop", "compare", "learn"
        ] = "explore",
        p=Depends(principal),
    ):
        return GraphService(get_container()).neighborhood(
            doc_id, category_id, depth, scenario
        )

    @app.post("/api/v1/graph/links")
    def save_link(req: Link, p=Depends(principal)):
        need(p, "writer")
        return GraphService(get_container()).save(
            p, req.source_id, req.target_id, req.kind, req.note
        )

    @app.delete("/api/v1/graph/links/{ident}")
    def delete_link(ident: str, p=Depends(principal)):
        need(p, "writer")
        return GraphService(get_container()).remove(p, ident)

    @app.post("/api/v1/classify")
    def classify(req: Classification, p=Depends(principal)):
        return agent().classify(req.title, req.content)

    @app.get("/api/v1/assistant/status")
    def status(p=Depends(principal)):
        return agent().public()

    @app.post("/api/v1/assistant/ask")
    def ask(req: Question, p=Depends(principal)):
        return agent().ask(**req.model_dump())

    @app.get("/api/v1/admin/assistant")
    def settings(p=Depends(principal)):
        need(p, "admin")
        return agent().public(admin=True)

    @app.put("/api/v1/admin/assistant")
    def save_settings(req: AgentSettings, p=Depends(principal)):
        need(p, "admin")
        return agent().save(**req.model_dump())
