"""业务服务层。

HTTP / MCP / CLI 三种入口全部调用这里，保证行为完全一致。
所有方法的返回值都是纯 dict/list，可以直接 JSON 序列化，
MCP 那边不用再转换一次。
"""

from __future__ import annotations

import re
import time
from typing import Any

from .container import Container
from .docs import DocInput, DocRepo
from .rules import render_brief, resolve_profile


class ServiceError(Exception):
    def __init__(self, code: str, message: str, hint: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint


class WorkbenchService:
    def __init__(self, c: Container) -> None:
        self.c = c

    # ================= 检索 =================

    def search(
        self,
        query: str,
        *,
        limit: int = 8,
        domain: str = "",
        source: str = "",
        tag: str = "",
        include_deprecated: bool = False,
    ) -> dict[str, Any]:
        if not query or not query.strip():
            raise ServiceError("empty_query", "query 不能为空", "传入中文关键词或问题描述")
        limit = max(1, min(limit, self.c.settings.max_top_k))
        hits = self.c.index.search(
            query,
            limit=limit,
            domain=domain or None,
            source=source or None,
            tag=tag or None,
            include_deprecated=include_deprecated,
        )
        items = [h.to_dict() for h in hits]
        out: dict[str, Any] = {
            "query": query,
            "count": len(items),
            "results": items,
        }
        if not items:
            out["hint"] = "无命中。可尝试：去掉'怎么做/如何'等虚词，直接用平台术语（SPI扩展/UDC/组织同步）；或调用 v8_domains 看有哪些知识域"
        elif items[0]["score"] < 2.0:
            out["hint"] = "命中较弱。建议用 v8_read 打开排名第一的文档确认，或换用更具体的平台术语重新检索"
        return out

    def read(
        self,
        doc_id: str = "",
        *,
        title: str = "",
        max_chars: int | None = None,
        offset: int = 0,
    ) -> dict[str, Any]:
        doc = None
        if doc_id:
            doc = self.c.repo.get(doc_id)
        elif title:
            cands = self.c.repo.find_by_title(title)
            if len(cands) == 1:
                doc = cands[0]
            elif len(cands) > 1:
                return {
                    "ambiguous": True,
                    "candidates": [
                        {"id": x["id"], "title": x["title"], "path": x["path_text"]} for x in cands
                    ],
                    "hint": "标题匹配到多篇，请用 id 精确读取",
                }
        if not doc:
            raise ServiceError("not_found", f"未找到文档：{doc_id or title}", "先用 v8_search 拿到 id")

        limit = min(max_chars or self.c.settings.max_read_chars, self.c.settings.max_read_chars)
        body = doc["body"]
        total = len(body)
        chunk = body[offset : offset + limit]
        return {
            "id": doc["id"],
            "title": doc["title"],
            "path": doc["path_text"],
            "domain": doc["domain"],
            "source": doc["source"],
            "url": doc["url"],
            "version_hint": doc["version_hint"],
            "tags": doc["tags"],
            "content": chunk,
            "offset": offset,
            "total_chars": total,
            "truncated": offset + limit < total,
            "next_offset": offset + limit if offset + limit < total else None,
        }

    def domains(self) -> dict[str, Any]:
        return {"domains": self.c.index.domains(), "total": sum(d["count"] for d in self.c.index.domains())}

    # ================= 规范 =================

    def rules(self, task: str = "", *, include_docs: bool = False, per_doc_chars: int = 6000) -> dict[str, Any]:
        p = resolve_profile(task)
        brief = render_brief(p)
        out: dict[str, Any] = {
            "profile": p.key,
            "name": p.name,
            "matched_by": task or "(默认通用)",
            "checklist": list(p.checklist),
            "pitfalls": list(p.pitfalls),
            "must_read_titles": list(p.must_read),
            "reference_titles": list(p.reference),
            "brief": brief,
        }
        if include_docs:
            out["documents"] = self._resolve_titles(p.must_read, per_doc_chars)
        else:
            # 即便不取正文，也把每篇的 id 带出来，agent 可直接 read
            out["documents_index"] = [
                {"title": d["title"], "id": d["id"], "chars": len(d["body"])}
                for d in self._lookup_titles(p.must_read)
            ]
        return out

    def _lookup_titles(self, titles: tuple[str, ...]) -> list[dict]:
        out = []
        for t in titles:
            rows = self.c.repo.find_by_title(t)
            # 精确标题优先
            exact = [r for r in rows if r["title"] == t]
            pick = (exact or rows or [None])[0]
            if pick:
                out.append(pick)
        return out

    def _resolve_titles(self, titles: tuple[str, ...], per_doc_chars: int) -> list[dict]:
        out = []
        for doc in self._lookup_titles(titles):
            out.append(
                {
                    "id": doc["id"],
                    "title": doc["title"],
                    "path": doc["path_text"],
                    "content": doc["body"][:per_doc_chars],
                    "truncated": len(doc["body"]) > per_doc_chars,
                }
            )
        return out

    # ================= 知识写入 =================

    def submit_knowledge(
        self,
        *,
        title: str,
        content: str,
        actor: str,
        source: str = "agent",
        path: str = "",
        tags: list[str] | None = None,
        summary: str = "",
        url: str = "",
        project: str = "",
        version_hint: str = "",
    ) -> dict[str, Any]:
        if len(content.strip()) < 20:
            raise ServiceError("too_short", "内容过短，至少 20 字符", "知识条目需要能独立看懂，请补充背景和结论")
        if source not in {"agent", "manual", "upload"}:
            raise ServiceError("bad_source", f"source 只能是 agent/manual/upload，收到 {source}")
        r = self.c.repo.upsert(
            DocInput(
                id=None,
                title=title.strip(),
                body=content,
                source=source,
                path_text=path or f"沉淀/{project}" if project else path,
                summary=summary,
                url=url,
                tags=tags or [],
                meta={"project": project} if project else {},
                created_by=actor,
                version_hint=version_hint,
            )
        )
        if r.action != "unchanged":
            self.c.rebuild_index()
        return {"id": r.doc_id, "action": r.action, "title": r.title}

    def delete_doc(self, doc_id: str, actor: str) -> dict[str, Any]:
        ok = self.c.repo.delete(doc_id, actor)
        if ok:
            self.c.rebuild_index()
        return {"deleted": ok, "id": doc_id}

    # ================= 运维/统计 =================

    def stats(self) -> dict[str, Any]:
        s = self.c.index.stats()
        s["by_source"] = self.c.repo.count_by_source()
        return s

    def health(self) -> dict[str, Any]:
        return {
            "ok": True,
            "version": "0.1.0",
            "documents": self.c.index.stats()["documents"],
            "time": time.time(),
        }

    def recent(self, limit: int = 20) -> dict[str, Any]:
        rows = self.c.db.query(
            """SELECT id, title, source, domain, created_by, updated_at
               FROM docs WHERE is_deprecated = 0
               ORDER BY updated_at DESC LIMIT ?""",
            (limit,),
        )
        return {"recent": [dict(r) for r in rows]}
