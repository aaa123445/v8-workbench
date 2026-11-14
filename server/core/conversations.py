"""Account-scoped, durable chat snapshots. Knowledge evidence stays with each answer."""
import json
import time

from .knowledge import KnowledgeError, actor_id


class ConversationService:
    def __init__(self, container):
        self.db = container.db

    def list(self, principal):
        rows = self.db.query(
            "SELECT id,title,updated_at FROM assistant_conversations WHERE owner=? ORDER BY updated_at DESC LIMIT 200",
            (actor_id(principal),),
        )
        return {"conversations": [dict(row) for row in rows]}

    def read(self, principal, ident):
        row = self.db.one(
            "SELECT * FROM assistant_conversations WHERE id=? AND owner=?",
            (ident, actor_id(principal)),
        )
        if not row:
            raise KnowledgeError("对话不存在或无权访问", 404)
        return {"id": row["id"], "title": row["title"], "updated_at": row["updated_at"], **json.loads(row["payload"])}

    def save(self, principal, ident, payload):
        encoded = json.dumps(payload, ensure_ascii=False)
        if len(encoded.encode("utf-8")) > 2_000_000:
            raise KnowledgeError("当前对话内容过长，请新建对话", 413)
        title = next((m["content"] for m in payload["messages"] if m["role"] == "user"), "新对话")[:80]
        owner, now = actor_id(principal), time.time()
        with self.db.write() as conn:
            existing = conn.execute("SELECT owner FROM assistant_conversations WHERE id=?", (ident,)).fetchone()
            if existing and existing["owner"] != owner:
                raise KnowledgeError("对话不存在或无权访问", 404)
            conn.execute(
                "INSERT INTO assistant_conversations(id,owner,title,payload,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,payload=excluded.payload,updated_at=excluded.updated_at",
                (ident, owner, title, encoded, now),
            )
        return {"id": ident, "title": title, "updated_at": now}
