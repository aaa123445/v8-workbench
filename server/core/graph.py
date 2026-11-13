"""Bounded knowledge neighborhoods: explicit links, wiki/Markdown citations and suggestions."""

from __future__ import annotations

import hashlib
import re
import time
from collections import defaultdict, deque
from urllib.parse import unquote

from .knowledge import KnowledgeError, actor_id

RELATIONS = {
    "related": "相关知识",
    "prerequisite": "前置知识",
    "solution": "问题与解法",
    "example": "应用示例",
    "contrast": "对比方案",
}
SCENARIOS = {
    "auto": "自动判断",
    "explore": "知识探索",
    "troubleshoot": "排障溯源",
    "develop": "开发实施",
    "compare": "方案对比",
    "learn": "学习路线",
}


def scenario_for(question, requested="auto"):
    if requested != "auto":
        return requested
    for key, pattern in [
        ("compare", r"对比|比较|区别|选型|优劣"),
        ("troubleshoot", r"报错|失败|异常|排查|原因|故障|404|500|不生效"),
        ("learn", r"入门|学习|路线|先学"),
        ("develop", r"实现|开发|集成|接入|部署|如何|怎么"),
    ]:
        if re.search(pattern, question, re.I):
            return key
    return "explore"


class GraphService:
    def __init__(self, container):
        self.c = container
        self.db = container.db

    def doc(self, did):
        row = self.db.one(
            "SELECT id,title,category_id,tags,url,body,knowledge_version FROM docs WHERE id=? AND is_deprecated=0",
            (did,),
        )
        if not row:
            raise KnowledgeError("文档不存在或已下架", 404)
        return dict(row)

    def save(self, p, source, target, kind, note=""):
        if kind not in RELATIONS or source == target:
            raise KnowledgeError("请选择有效关系，不能关联文档自身")
        self.doc(source)
        self.doc(target)
        # A relation is shared editorial metadata, author/admin may remove it.
        ident = hashlib.sha256(
            (source + "\n" + target + "\n" + kind).encode()
        ).hexdigest()[:24]
        owner = actor_id(p)
        with self.db.write() as conn:
            existing = conn.execute(
                "SELECT * FROM knowledge_links WHERE id=?", (ident,)
            ).fetchone()
            if existing and existing["actor"] != owner and not p.can("admin"):
                raise KnowledgeError("此关系由其他成员维护，请联系作者或管理员", 403)
            conn.execute(
                "INSERT INTO knowledge_links(id,source_id,target_id,kind,note,actor,created_at) VALUES (?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET note=excluded.note",
                (ident, source, target, kind, note, owner, time.time()),
            )
            conn.execute(
                "INSERT INTO knowledge_audit(actor,action,target,details,created_at) VALUES (?,?,?,?,?)",
                (owner, "link_save", ident, kind, time.time()),
            )
        return {"id": ident}

    def remove(self, p, ident):
        with self.db.write() as conn:
            row = conn.execute(
                "SELECT actor FROM knowledge_links WHERE id=?", (ident,)
            ).fetchone()
            if not row:
                raise KnowledgeError("关系不存在", 404)
            if row["actor"] != actor_id(p) and not p.can("admin"):
                raise KnowledgeError("只能删除自己创建的关系", 403)
            conn.execute("DELETE FROM knowledge_links WHERE id=?", (ident,))
            conn.execute(
                "INSERT INTO knowledge_audit(actor,action,target,details,created_at) VALUES (?,?,?,?,?)",
                (actor_id(p), "link_delete", ident, "{}", time.time()),
            )
        return {"deleted": True}

    def _catalog(self, category_id=""):
        rows = [
            dict(r)
            for r in self.db.query(
                "SELECT id,title,category_id,tags,url,body,knowledge_version FROM docs WHERE is_deprecated=0 ORDER BY id"
            )
        ]
        if category_id:
            allowed = self.c.knowledge.descendants(category_id)
            rows = [r for r in rows if r["category_id"] in allowed]
        return {r["id"]: r for r in rows}

    def _edges(self, catalog):
        edges = []
        for r in self.db.query("SELECT * FROM knowledge_links ORDER BY created_at,id"):
            if r["source_id"] in catalog and r["target_id"] in catalog:
                edges.append(
                    {**dict(r), "origin": "manual", "label": RELATIONS[r["kind"]]}
                )
        titles = defaultdict(list)
        urls = defaultdict(list)
        for d in catalog.values():
            titles[d["title"].casefold()].append(d["id"])
            if d["url"]:
                urls[d["url"]].append(d["id"])
        seen = set()
        for d in catalog.values():
            targets = set()
            # Examples inside fenced code are not actual knowledge references.
            body = re.sub(
                r"(?ms)^```[^\n]*\n.*?^```[^\n]*$|^~~~[^\n]*\n.*?^~~~[^\n]*$",
                "",
                d["body"],
            )
            for name in re.findall(r"\[\[([^\]\n]+)\]\]", body):
                name = name.split("|", 1)[0].split("#", 1)[0].strip()
                matches = [name] if name in catalog else titles.get(name.casefold(), [])
                if len(matches) == 1:
                    targets.add(matches[0])
            for url in re.findall(r"(?<!!)\[[^\]\n]*\]\(([^\s)]+)\)", body):
                matches = urls.get(url, [])
                if "/documents/" in url:
                    ident = unquote(
                        url.split("/documents/", 1)[1].split("?", 1)[0].split("#", 1)[0]
                    )
                    if ident in catalog:
                        matches = [ident]
                if len(matches) == 1:
                    targets.add(matches[0])
            for target in sorted(targets):
                if target == d["id"] or (d["id"], target) in seen:
                    continue
                seen.add((d["id"], target))
                edges.append(
                    {
                        "id": "ref:" + d["id"] + ":" + target,
                        "source_id": d["id"],
                        "target_id": target,
                        "kind": "reference",
                        "label": "文档引用",
                        "origin": "reference",
                        "note": "由正文双链或文档链接识别",
                        "actor": "",
                    }
                )
        return edges

    @staticmethod
    def node(d):
        return {k: d[k] for k in ("id", "title", "category_id", "knowledge_version")}

    def all_graph(self, category_id="", limit=5000):
        catalog = self._catalog(category_id)
        edges = self._edges(catalog)
        # Only documents participating in an explicit/reference relation enter the graph.
        connected = {e["source_id"] for e in edges} | {e["target_id"] for e in edges}
        if not connected:
            return {
                "center": "",
                "nodes": [],
                "edges": [],
                "suggestions": [],
                "categories": self.c.knowledge.categories(),
                "truncated": False,
            }
        ordered = sorted(connected, key=lambda ident: (catalog[ident]["title"], ident))
        truncated = len(ordered) > limit
        allowed = set(ordered[:limit])
        selected_edges = [
            e for e in edges if e["source_id"] in allowed and e["target_id"] in allowed
        ]
        return {
            "center": ordered[0],
            "nodes": [self.node(catalog[x]) for x in ordered[:limit]],
            "edges": selected_edges,
            "suggestions": [],
            "categories": self.c.knowledge.categories(),
            "truncated": truncated,
        }

    def neighborhood(self, doc_id, category_id="", depth=1, scenario="explore"):
        catalog = self._catalog(category_id)
        if doc_id not in catalog:
            raise KnowledgeError("当前分类内没有这篇文档", 404)
        edges = self._edges(catalog)
        adjacent = defaultdict(list)
        for edge in edges:
            adjacent[edge["source_id"]].append(edge)
            adjacent[edge["target_id"]].append(edge)
        selected = {doc_id}
        queue = deque([(doc_id, 0)])
        used = {}
        while queue:
            ident, level = queue.popleft()
            if level >= depth:
                continue
            ordered = sorted(
                adjacent[ident], key=lambda e: (e["origin"] != "manual", e["id"])
            )
            for edge in ordered:
                other = (
                    edge["target_id"]
                    if edge["source_id"] == ident
                    else edge["source_id"]
                )
                if other not in selected and len(selected) >= 24:
                    continue
                used[edge["id"]] = edge
                if other not in selected:
                    selected.add(other)
                    queue.append((other, level + 1))
        # Similarity is a recommendation, never a persisted or verified link.
        seed = catalog[doc_id]
        query = seed["title"][:100]
        hits = self.c.index.search(
            query, limit=16, category_ids={d["category_id"] for d in catalog.values()}
        )
        suggestions = []
        for hit in hits:
            ident = hit.doc.id
            if ident in selected or ident not in catalog:
                continue
            suggestions.append(
                {
                    **self.node(catalog[ident]),
                    "reason": "标题与内容关键词匹配"
                    + (
                        "，属于同一分类"
                        if catalog[ident]["category_id"] == seed["category_id"]
                        else "，来自其他分类"
                    ),
                    "score": round(hit.score, 2),
                }
            )
            if len(suggestions) == 6:
                break
        priorities = {
            "learn": "prerequisite",
            "develop": "example",
            "troubleshoot": "solution",
            "compare": "contrast",
        }
        ordered_edges = sorted(
            used.values(),
            key=lambda e: (
                e["kind"] != priorities.get(scenario),
                e["origin"] != "manual",
                e["id"],
            ),
        )
        # Order is a suggested reading sequence, not an execution plan.
        ordered_ids = [doc_id]
        for edge in ordered_edges:
            pair = (
                [edge["target_id"], edge["source_id"]]
                if edge["kind"] == "prerequisite" and scenario == "learn"
                else [edge["source_id"], edge["target_id"]]
            )
            for ident in pair:
                if ident not in ordered_ids:
                    ordered_ids.append(ident)
        if scenario == "learn":
            prerequisites = [
                e["target_id"]
                for e in ordered_edges
                if e["source_id"] == doc_id and e["kind"] == "prerequisite"
            ]
            ordered_ids = list(dict.fromkeys(prerequisites + ordered_ids))
        return {
            "reading_order": [self.node(catalog[x]) for x in ordered_ids[:12]],
            "center": doc_id,
            "nodes": [
                self.node(catalog[x]) for x in [doc_id] + sorted(selected - {doc_id})
            ],
            "edges": ordered_edges[:60],
            "suggestions": suggestions,
            "scenario": scenario,
            "limit": 24,
            "truncated": len(selected) >= 24,
            "categories": [
                {"id": c["id"], "name": c["name"], "path": c["path"]}
                for c in self.c.knowledge.categories()
            ],
        }
