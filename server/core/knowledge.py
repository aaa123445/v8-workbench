"""Generic taxonomy, reviewed contributions, immutable versions and rule collections."""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import time
from difflib import SequenceMatcher

from .v8_categories import initialize_v8_categories


class KnowledgeError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


DEFAULT_CATEGORIES = [
    ("technology", "技术开发", None),
    ("frontend", "前端", "technology"),
    ("backend", "后端", "technology"),
    ("database", "数据库", "technology"),
    ("operations", "运维部署", "technology"),
    ("business", "产品与业务", None),
    ("projects", "项目实践", None),
    ("standards", "团队规范", None),
    ("platforms", "技术平台", None),
    ("seeyon-v8", "致远 V8", "platforms"),
    ("uncategorized", "待分类", None),
]


def fingerprint(title, content):
    return hashlib.sha256(
        (title.strip() + "\n" + content.replace("\r\n", "\n").strip()).encode()
    ).hexdigest()


def actor_id(p):
    return "user:" + p.user_id if p.user_id else "key:" + p.key_prefix


def safe_payload(value):
    # Never accept credentials as part of a knowledge contribution.
    text = json.dumps(value, ensure_ascii=False)
    if re.search(
        r"wb_(?:rd|wr|ad)_[A-Za-z0-9_-]{16,}|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|\b(?:sk-proj-|sk-live-|ghp_|github_pat_)[A-Za-z0-9_-]{16,}",
        text,
    ):
        raise KnowledgeError("内容中包含疑似凭据，请在本地脱敏后提交")
    return value


class KnowledgeService:
    def __init__(self, container):
        self.c = container
        self.db = container.db
        self.bootstrap()

    def bootstrap(self):
        with self.db.write() as conn:
            for i, (cid, name, parent) in enumerate(DEFAULT_CATEGORIES):
                conn.execute(
                    "INSERT OR IGNORE INTO categories(id,name,parent_id,sort_order,created_at) VALUES (?,?,?,?,?)",
                    (cid, name, parent, i, time.time()),
                )
            # One-time, additive assignment. IDs, source paths and bodies stay stable.
            conn.execute(
                "UPDATE docs SET category_id=CASE WHEN source='yuque' OR id LIKE 'yuque:%' THEN 'seeyon-v8' ELSE 'uncategorized' END WHERE category_id IS NULL OR category_id=''"
            )
            initialize_v8_categories(conn)
            rows = conn.execute(
                "SELECT * FROM docs d WHERE NOT EXISTS(SELECT 1 FROM knowledge_versions v WHERE v.doc_id=d.id)"
            ).fetchall()
            for row in rows:
                conn.execute(
                    "INSERT INTO knowledge_versions(doc_id,version,title,content,category_id,tags,summary,version_hint,url,actor,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        row["id"],
                        1,
                        row["title"],
                        row["body"],
                        row["category_id"],
                        row["tags"],
                        row["summary"],
                        row["version_hint"],
                        row["url"],
                        "migration",
                        row["updated_at"],
                    ),
                )

    def categories(self):
        rows = [
            dict(r)
            for r in self.db.query(
                "SELECT c.*, (SELECT COUNT(*) FROM docs d WHERE d.category_id=c.id AND d.is_deprecated=0) AS documents FROM categories c ORDER BY sort_order,name"
            )
        ]
        by_id = {row["id"]: row for row in rows}

        def path(row):
            return (
                path(by_id[row["parent_id"]]) + " / "
                if row["parent_id"] in by_id
                else ""
            ) + row["name"]

        for row in rows:
            row["path"] = path(row)
        children = {}
        for row in rows:
            children.setdefault(row["parent_id"], []).append(row)
        ordered = []

        def visit(row):
            ordered.append(row)
            total = row["documents"]
            for child in children.get(row["id"], []):
                total += visit(child)
            row["total_documents"] = total
            return total

        for row in children.get(None, []):
            visit(row)
        return ordered

    def descendants(self, cid):
        if not self.db.one("SELECT 1 FROM categories WHERE id=?", (cid,)):
            raise KnowledgeError("分类不存在", 404)
        return [
            row["id"]
            for row in self.db.query(
                "WITH RECURSIVE tree(id) AS (SELECT id FROM categories WHERE id=? UNION ALL SELECT c.id FROM categories c JOIN tree t ON c.parent_id=t.id) SELECT id FROM tree",
                (cid,),
            )
        ]

    def category_path(self, cid):
        row = next((r for r in self.categories() if r["id"] == cid), None)
        if not row:
            raise KnowledgeError("分类不存在", 404)
        return row["path"]

    def save_category(self, name, parent_id=None, cid=None):
        name = name.strip()
        if not name or len(name) > 60:
            raise KnowledgeError("分类名称需要 1–60 个字符")
        with self.db.write() as conn:
            if parent_id:
                self.descendants(parent_id)
            if cid:
                descendants = self.descendants(cid)
                if parent_id in descendants:
                    raise KnowledgeError("分类不能移动到自身或子分类下")
            else:
                cid = "cat_" + secrets.token_hex(8)
            duplicate = conn.execute(
                "SELECT id FROM categories WHERE name=? AND COALESCE(parent_id,'')=COALESCE(?,'') AND id!=?",
                (name, parent_id, cid),
            ).fetchone()
            if duplicate:
                raise KnowledgeError("同级分类名称已存在")
            conn.execute(
                "INSERT INTO categories(id,name,parent_id,created_at) VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,parent_id=excluded.parent_id",
                (cid, name, parent_id, time.time()),
            )
        return {"id": cid}

    def delete_category(self, cid):
        if cid in {item[0] for item in DEFAULT_CATEGORIES}:
            raise KnowledgeError("基础分类不能删除，可调整名称或层级")
        with self.db.write() as conn:
            if conn.execute(
                "SELECT 1 FROM categories WHERE parent_id=?", (cid,)
            ).fetchone():
                raise KnowledgeError("请先移动或删除子分类")
            if (
                conn.execute(
                    "SELECT 1 FROM docs WHERE category_id=?", (cid,)
                ).fetchone()
                or conn.execute(
                    "SELECT 1 FROM contributions WHERE category_id=?", (cid,)
                ).fetchone()
                or conn.execute(
                    "SELECT 1 FROM rule_sets WHERE category_id=?", (cid,)
                ).fetchone()
                or conn.execute(
                    "SELECT 1 FROM knowledge_versions WHERE category_id=?", (cid,)
                ).fetchone()
            ):
                raise KnowledgeError("分类仍有关联内容，请先移动内容")
            return {
                "deleted": bool(
                    conn.execute("DELETE FROM categories WHERE id=?", (cid,)).rowcount
                )
            }

    def browse(
        self, category_id="", query="", tag="", page=1, page_size=20, sort="updated"
    ):
        where = ["is_deprecated=0"]
        args = []
        if category_id:
            ids = self.descendants(category_id)
            where.append("category_id IN (" + ",".join("?" for _ in ids) + ")")
            args.extend(ids)
        if query:
            where.append("(title LIKE ? OR summary LIKE ?)")
            args.extend(["%" + query + "%"] * 2)
        if tag:
            where.append("EXISTS(SELECT 1 FROM json_each(docs.tags) WHERE value=?)")
            args.append(tag)
        sql = " AND ".join(where)
        total = self.db.scalar("SELECT COUNT(*) FROM docs WHERE " + sql, tuple(args))
        order = {
            "updated": "updated_at DESC,id",
            "oldest": "updated_at ASC,id",
            "title": "title COLLATE NOCASE,id",
        }.get(sort, "updated_at DESC,id")
        rows = self.db.query(
            "SELECT id,title,summary,category_id,source,tags,version_hint,updated_at FROM docs WHERE "
            + sql
            + " ORDER BY "
            + order
            + " LIMIT ? OFFSET ?",
            (*args, page_size, (page - 1) * page_size),
        )
        data = [dict(r) for r in rows]
        for row in data:
            row["tags"] = json.loads(row["tags"])
        return {"documents": data, "total": total, "page": page, "page_size": page_size}

    def quality(self, payload):
        checks = {
            "problem": len(payload.get("problem", "").strip()) >= 10,
            "solution": len(payload.get("solution", "").strip()) >= 20,
            "verification": payload.get("verified") is True
            and len(payload.get("verification", "").strip()) >= 10,
            "limitations": len(payload.get("limitations", "").strip()) >= 5,
            "reusable": payload.get("reusable") is True,
            "content": len(payload.get("content", "").strip()) >= 80,
        }
        return {
            "eligible": all(checks.values()),
            "checks": checks,
            "missing": [k for k, v in checks.items() if not v],
        }

    def similar(self, title, content, exclude=""):
        hits = []
        fp = fingerprint(title, content)
        for row in self.db.query(
            "SELECT id,title,body FROM docs WHERE is_deprecated=0"
        ):
            if row["id"] == exclude:
                continue
            exact = fingerprint(row["title"], row["body"]) == fp
            score = (
                1.0
                if exact
                else SequenceMatcher(
                    None, title.strip().lower(), row["title"].strip().lower()
                ).ratio()
            )
            if exact or score >= 0.6:
                hits.append(
                    {
                        "id": row["id"],
                        "title": row["title"],
                        "similarity": round(score, 3),
                        "exact": exact,
                    }
                )
        return sorted(hits, key=lambda x: x["similarity"], reverse=True)[:5]

    def _own(self, p, row):
        return row["owner_id"] == actor_id(p)

    def _public(self, row, full=True):
        out = dict(row)
        for k in ["tags", "quality", "similar", "payload"]:
            out[k] = json.loads(out[k])
        if not full:
            out.pop("content", None)
            out.pop("payload", None)
        return out

    def propose(self, p, payload, submit=True, contribution_id=None):
        safe_payload(payload)
        title = payload.get("title", "").strip()
        content = payload.get("content", "").strip()
        if not title or len(title) > 300 or len(content) < 20:
            raise KnowledgeError("请填写标题，正文至少 20 字符")
        cid = payload.get("category_id") or "uncategorized"
        self.category_path(cid)
        target = payload.get("target_doc_id") or ""
        target_row = (
            self.db.one("SELECT * FROM docs WHERE id=? AND is_deprecated=0", (target,))
            if target
            else None
        )
        if target and not target_row:
            raise KnowledgeError("更新目标文档不存在", 404)
        if target and payload.get("base_version") != target_row["knowledge_version"]:
            raise KnowledgeError(
                "更新目标的版本已变化或未指定 base_version，请阅读最新文档后重新合并提交",
                409,
            )
        fp = fingerprint(title, content)
        similar = self.similar(title, content, target)
        is_agent = payload.get("source") == "agent"
        quality = self.quality(payload)
        if submit and is_agent and not quality["eligible"]:
            raise KnowledgeError(
                "自动沉淀材料不完整：" + ", ".join(quality["missing"]), 422
            )
        now = time.time()
        owner = actor_id(p)
        with self.db.write() as conn:
            if contribution_id:
                old = conn.execute(
                    "SELECT * FROM contributions WHERE id=?", (contribution_id,)
                ).fetchone()
                if not old or not self._own(p, old):
                    raise KnowledgeError("贡献不存在", 404)
                if old["status"] not in {"draft", "changes_requested"}:
                    raise KnowledgeError("只有草稿或需修改的内容可以编辑", 409)
            else:
                previous = conn.execute(
                    "SELECT * FROM contributions WHERE owner_id=? AND fingerprint=? AND COALESCE(target_doc_id,'')=? AND status IN ('draft','pending','published') ORDER BY updated_at DESC LIMIT 1",
                    (owner, fp, target),
                ).fetchone()
                if previous and not (submit and previous["status"] == "draft"):
                    return {**self._public(previous), "action": "unchanged"}
                if previous:
                    contribution_id = previous["id"]
                    old = previous
                else:
                    contribution_id = "con_" + secrets.token_hex(12)
                    old = None
            if submit and any(x["exact"] for x in similar):
                return {
                    "action": "duplicate",
                    "status": "duplicate",
                    "duplicate": next(x for x in similar if x["exact"]),
                    "similar": similar,
                }
            state = "pending" if submit else "draft"
            base = target_row["knowledge_version"] if target_row else 0
            # An edited update keeps the originally reviewed base unless resubmitted.
            fields = (
                owner,
                p.user_id,
                p.key_prefix,
                title,
                content,
                cid,
                json.dumps(payload.get("tags", []), ensure_ascii=False),
                payload.get("summary", ""),
                payload.get("source", "manual"),
                target or None,
                base,
                fp,
                state,
                json.dumps(payload, ensure_ascii=False),
                json.dumps(quality),
                json.dumps(similar, ensure_ascii=False),
                now,
                now,
                contribution_id,
            )
            conn.execute(
                """INSERT INTO contributions(owner_id,user_id,key_prefix,title,content,category_id,tags,summary,source,target_doc_id,base_version,fingerprint,status,payload,quality,similar,created_at,updated_at,id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,content=excluded.content,category_id=excluded.category_id,tags=excluded.tags,summary=excluded.summary,source=excluded.source,target_doc_id=excluded.target_doc_id,base_version=excluded.base_version,fingerprint=excluded.fingerprint,status=excluded.status,payload=excluded.payload,quality=excluded.quality,similar=excluded.similar,updated_at=excluded.updated_at""",
                fields,
            )
            conn.execute(
                "INSERT INTO contribution_events(contribution_id,actor,action,note,created_at) VALUES (?,?,?,?,?)",
                (contribution_id, owner, "submit" if submit else "save", "", now),
            )
        key_policy = (
            self.db.one(
                "SELECT auto_publish FROM api_keys WHERE key_prefix=?", (p.key_prefix,)
            )
            if p.kind == "key"
            else None
        )
        if (
            submit
            and is_agent
            and quality["eligible"]
            and key_policy
            and key_policy["auto_publish"]
            and not similar
            and not target
        ):
            self.review(
                p, contribution_id, "publish", "可信 Agent 自动发布", trusted=True
            )
        return {
            **self.contribution(p, contribution_id),
            "action": "updated" if old else "created",
        }

    def contribution(self, p, cid):
        row = self.db.one("SELECT * FROM contributions WHERE id=?", (cid,))
        if not row or not (self._own(p, row) or p.can("admin")):
            raise KnowledgeError("贡献不存在", 404)
        out = self._public(row)
        out["events"] = [
            dict(r)
            for r in self.db.query(
                "SELECT * FROM contribution_events WHERE contribution_id=? ORDER BY id",
                (cid,),
            )
        ]
        return out

    def contributions(self, p, status="", page=1, page_size=20, review=False):
        where = []
        args = []
        if review and not p.can("admin"):
            raise KnowledgeError("需要管理员权限", 403)
        if not review:
            where.append("owner_id=?")
            args.append(actor_id(p))
        if status:
            where.append("status=?")
            args.append(status)
        sql = " AND ".join(where) or "1=1"
        total = self.db.scalar(
            "SELECT COUNT(*) FROM contributions WHERE " + sql, tuple(args)
        )
        rows = self.db.query(
            "SELECT * FROM contributions WHERE "
            + sql
            + " ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (*args, page_size, (page - 1) * page_size),
        )
        return {
            "items": [self._public(row, False) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def review(self, p, cid, action, note="", trusted=False):
        if not trusted and not p.can("admin"):
            raise KnowledgeError("需要管理员审核权限", 403)
        if action not in {"publish", "changes_requested", "reject"}:
            raise KnowledgeError("无效的审核操作")
        with self.db.write() as conn:
            row = conn.execute(
                "SELECT * FROM contributions WHERE id=?", (cid,)
            ).fetchone()
            if not row:
                raise KnowledgeError("贡献不存在", 404)
            if row["status"] != "pending":
                raise KnowledgeError("此贡献不在待审核状态", 409)
            if trusted:
                policy = conn.execute(
                    "SELECT auto_publish,enabled FROM api_keys WHERE key_prefix=?",
                    (p.key_prefix,),
                ).fetchone()
                if not (
                    p.kind == "key"
                    and p.can("writer")
                    and policy
                    and policy["enabled"]
                    and policy["auto_publish"]
                    and self._own(p, row)
                    and not row["target_doc_id"]
                    and row["source"] == "agent"
                    and self.quality(json.loads(row["payload"]))["eligible"]
                    and not self.similar(
                        row["title"], row["content"], row["target_doc_id"] or ""
                    )
                ):
                    raise KnowledgeError("自动发布条件已变化，请交由管理员审核", 409)
            state = {
                "publish": "published",
                "changes_requested": "changes_requested",
                "reject": "rejected",
            }[action]
            doc_id = row["target_doc_id"] or "kb:" + secrets.token_hex(12)
            if action == "publish":
                current = conn.execute(
                    "SELECT * FROM docs WHERE id=?", (doc_id,)
                ).fetchone()
                if row["target_doc_id"] and (
                    not current or current["knowledge_version"] != row["base_version"]
                ):
                    raise KnowledgeError(
                        "目标文档已变更，请退回贡献并重新提交更新建议", 409
                    )
                duplicates = self.similar(row["title"], row["content"], doc_id)
                if any(item["exact"] for item in duplicates):
                    raise KnowledgeError(
                        "已有相同知识，请拒绝重复贡献并关联现有文档", 409
                    )
                self._write_published(
                    conn,
                    doc_id,
                    row["title"],
                    row["content"],
                    row["category_id"],
                    row["tags"],
                    row["summary"],
                    json.loads(row["payload"]).get("version_hint", ""),
                    json.loads(row["payload"]).get("url", ""),
                    row["source"],
                    actor_id(p),
                )
            conn.execute(
                "UPDATE contributions SET status=?,review_note=?,reviewed_by=?,published_doc_id=?,updated_at=? WHERE id=?",
                (
                    state,
                    note,
                    actor_id(p),
                    doc_id if action == "publish" else None,
                    time.time(),
                    cid,
                ),
            )
            conn.execute(
                "INSERT INTO contribution_events(contribution_id,actor,action,note,created_at) VALUES (?,?,?,?,?)",
                (cid, actor_id(p), action, note, time.time()),
            )
        if action == "publish":
            self.c.rebuild_index()
        return self.contribution(p, cid)

    def _write_published(
        self,
        conn,
        doc_id,
        title,
        content,
        category_id,
        tags,
        summary,
        version_hint,
        url,
        source,
        actor,
    ):
        current = conn.execute(
            "SELECT knowledge_version FROM docs WHERE id=?", (doc_id,)
        ).fetchone()
        version = (current["knowledge_version"] if current else 0) + 1
        path = self.category_path(category_id).replace(" / ", " > ")
        now = time.time()
        checksum = fingerprint(title, content)[:32]
        conn.execute(
            """INSERT INTO docs(id,source,title,path_text,domain,body,summary,words,url,version_hint,tags,meta,checksum,created_by,created_at,updated_at,is_deprecated,category_id,knowledge_version) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,path_text=excluded.path_text,domain=excluded.domain,body=excluded.body,summary=excluded.summary,words=excluded.words,url=excluded.url,version_hint=excluded.version_hint,tags=excluded.tags,checksum=excluded.checksum,updated_at=excluded.updated_at,is_deprecated=0,category_id=excluded.category_id,knowledge_version=excluded.knowledge_version""",
            (
                doc_id,
                source,
                title,
                path,
                path.split(" > ")[0],
                content,
                summary or content[:240],
                len(content),
                url,
                version_hint,
                tags,
                "{}",
                checksum,
                actor,
                now,
                now,
                category_id,
                version,
            ),
        )
        conn.execute(
            "INSERT OR REPLACE INTO doc_fts(id,text) VALUES (?,?)",
            (doc_id, title + "\n" + path + "\n" + content),
        )
        conn.execute(
            "INSERT INTO knowledge_versions(doc_id,version,title,content,category_id,tags,summary,version_hint,url,actor,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                doc_id,
                version,
                title,
                content,
                category_id,
                tags,
                summary,
                version_hint,
                url,
                actor,
                now,
            ),
        )

    def versions(self, doc_id):
        if not self.db.one("SELECT 1 FROM docs WHERE id=?", (doc_id,)):
            raise KnowledgeError("文档不存在", 404)
        return [
            dict(r)
            for r in self.db.query(
                "SELECT version,title,actor,created_at FROM knowledge_versions WHERE doc_id=? ORDER BY version DESC",
                (doc_id,),
            )
        ]

    def version(self, doc_id, number):
        row = self.db.one(
            "SELECT * FROM knowledge_versions WHERE doc_id=? AND version=?",
            (doc_id, number),
        )
        if not row:
            raise KnowledgeError("版本不存在", 404)
        return dict(row)

    def rollback(self, p, doc_id, number, expected):
        if not p.can("admin"):
            raise KnowledgeError("需要管理员权限", 403)
        with self.db.write() as conn:
            current = conn.execute(
                "SELECT knowledge_version,source FROM docs WHERE id=?", (doc_id,)
            ).fetchone()
            if not current:
                raise KnowledgeError("文档不存在", 404)
            if current["knowledge_version"] != expected:
                raise KnowledgeError("文档版本已变更，请刷新后重试", 409)
            version = self.version(doc_id, number)
            self._write_published(
                conn,
                doc_id,
                version["title"],
                version["content"],
                version["category_id"],
                version["tags"],
                version["summary"],
                version["version_hint"],
                version["url"],
                current["source"],
                actor_id(p),
            )
        self.c.rebuild_index()
        return {"id": doc_id, "version": expected + 1}

    def standards(self, category_id=""):
        rows = self.db.query("SELECT * FROM rule_sets ORDER BY updated_at DESC")
        ids = self.descendants(category_id) if category_id else None
        return [
            {
                **dict(r),
                "checklist": json.loads(r["checklist"]),
                "doc_ids": json.loads(r["doc_ids"]),
            }
            for r in rows
            if not ids or r["category_id"] in ids
        ]

    def save_standard(self, p, payload, rid=None):
        if not p.can("admin"):
            raise KnowledgeError("需要管理员权限", 403)
        cid = payload.get("category_id") or "standards"
        self.category_path(cid)
        for did in payload.get("doc_ids", []):
            if not self.db.one(
                "SELECT 1 FROM docs WHERE id=? AND is_deprecated=0", (did,)
            ):
                raise KnowledgeError("关联文档不存在：" + did)
        rid = rid or "rule_" + secrets.token_hex(8)
        with self.db.write() as conn:
            conn.execute(
                "INSERT INTO rule_sets(id,name,category_id,description,checklist,doc_ids,updated_at,actor) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,category_id=excluded.category_id,description=excluded.description,checklist=excluded.checklist,doc_ids=excluded.doc_ids,updated_at=excluded.updated_at,actor=excluded.actor",
                (
                    rid,
                    payload["name"].strip(),
                    cid,
                    payload.get("description", ""),
                    json.dumps(payload.get("checklist", []), ensure_ascii=False),
                    json.dumps(payload.get("doc_ids", [])),
                    time.time(),
                    actor_id(p),
                ),
            )
            conn.execute(
                "INSERT INTO knowledge_audit(actor,action,target,details,created_at) VALUES (?,?,?,?,?)",
                (
                    actor_id(p),
                    "standard_save",
                    rid,
                    json.dumps(payload, ensure_ascii=False),
                    time.time(),
                ),
            )
        return {"id": rid}
