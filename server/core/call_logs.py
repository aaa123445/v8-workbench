"""Owner-scoped, bounded request/result history, independent of quota counters."""

from __future__ import annotations

import json
import re
import time
from typing import Any

from .auth import Principal
from .db import Database

REQUEST_LIMIT = 16 * 1024
RESPONSE_LIMIT = 64 * 1024
REQUEST_CAPTURE_LIMIT = 256 * 1024
RESPONSE_CAPTURE_LIMIT = 512 * 1024
REDACTED = "[已隐藏]"
SENSITIVE = {
    "authorization",
    "password",
    "currentpassword",
    "newpassword",
    "confirmpassword",
    "token",
    "accesstoken",
    "refreshtoken",
    "apikey",
    "key",
    "secret",
    "clientsecret",
    "cookie",
    "setcookie",
    "bootstrapadminkey",
}
_KEY_PATTERN = re.compile(r"wb_(?:rd|wr|ad)_[A-Za-z0-9_-]{6,}")
_BEARER_PATTERN = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]+={0,2}", re.I)
_FIELD_PATTERN = re.compile(
    r'("(?:authorization|password|current_password|new_password|token|access_token|refresh_token|api_key|key|secret|cookie|client_secret)"\s*:\s*)"(?:\\.|[^"\\])*"',
    re.I,
)
_URL_SECRET = re.compile(
    r"([?&](?:token|api[_-]?key|password|secret|access_token)=)[^&#\s]+", re.I
)

OPERATIONS = {
    ("GET", "/api/v1/graph"): "graph",
    ("GET", "/api/v1/graph/all"): "graph",
    ("POST", "/api/v1/graph/links"): "link",
    ("POST", "/api/v1/classify"): "classify",
    ("POST", "/api/v1/assistant/ask"): "ask",
    ("POST", "/api/v1/contributions"): "propose",
    ("GET", "/api/v1/categories"): "categories",
    ("GET", "/api/v1/library"): "library",
    ("GET", "/api/v1/standards"): "standards",
    ("POST", "/api/v1/search"): "search",
    ("POST", "/api/v1/read"): "read",
    ("POST", "/api/v1/rules"): "rules",
    ("GET", "/api/v1/domains"): "domains",
    ("GET", "/api/v1/stats"): "stats",
    ("GET", "/api/v1/recent"): "recent",
    ("POST", "/api/v1/knowledge"): "submit",
    ("POST", "/api/v1/knowledge/batch"): "submit_batch",
    ("POST", "/api/v1/admin/sync/yuque"): "sync",
    ("POST", "/api/v1/admin/rebuild"): "rebuild",
}


def operation_for(method: str, path: str) -> str | None:
    if method == "DELETE" and path.startswith("/api/v1/graph/links/"):
        return "unlink"
    if method in {"POST", "PUT"} and path.startswith("/api/v1/contributions/"):
        return "review" if path.endswith("/review") else "propose"
    if (
        method == "POST"
        and path.startswith("/api/v1/versions/")
        and path.endswith("/rollback")
    ):
        return "rollback"
    if method == "DELETE" and path.startswith("/api/v1/knowledge/"):
        return "delete"
    return OPERATIONS.get((method, path))


def clean_text(value: str) -> str:
    value = _KEY_PATTERN.sub(REDACTED, value)
    value = _BEARER_PATTERN.sub("Bearer " + REDACTED, value)
    value = _FIELD_PATTERN.sub(
        lambda m: m[1] + json.dumps(REDACTED, ensure_ascii=False), value
    )
    return _URL_SECRET.sub(lambda m: m[1] + REDACTED, value)


def redact(value: Any, depth=0) -> Any:
    if depth > 12:
        return "[嵌套内容已截断]"
    if isinstance(value, dict):
        return {
            k: REDACTED
            if re.sub(r"[^a-z]", "", k.lower()) in SENSITIVE
            else redact(v, depth + 1)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v, depth + 1) for v in value]
    if isinstance(value, str):
        return clean_text(value)
    return value


def snapshot(body: bytes, total: int, limit: int) -> tuple[Any, bool]:
    truncated = total > limit
    if not body:
        return None, truncated
    # Parse a bounded complete JSON object before truncating, so secret fields
    # cannot leak just because a truncated JSON prefix is no longer parseable.
    if total > len(body):
        return {"preview": "内容超过采集上限，原始正文未保存"}, True
    text = body.decode("utf-8", errors="replace")
    try:
        value = redact(json.loads(text))
    except (ValueError, RecursionError):
        return {"preview": "无法解析 JSON，原始正文未保存"}, truncated
    encoded = json.dumps(value, ensure_ascii=False)
    if len(encoded.encode()) > limit:
        # Reserve room for JSON quoting; a preview can at most double in size.
        prefix = encoded.encode()[: max(0, limit // 2 - 64)].decode(
            "utf-8", errors="replace"
        )
        value = {"preview": prefix}
        truncated = True
    return value, truncated


def outcome_for(status: int, result: Any) -> str:
    if status >= 400:
        return "failed"
    if isinstance(result, dict) and result.get("failed"):
        successful = result.get("count", result.get("fetched", 0))
        return "partial" if successful else "failed"
    return "success"


def summarize_request(operation: str, data: Any) -> str:
    if isinstance(data, dict):
        for key in ("query", "title", "task", "id"):
            if data.get(key):
                return clean_text(str(data[key]))[:240]
    if isinstance(data, list):
        return f"批量提交 {len(data)} 条知识"
    return {
        "stats": "查看知识统计",
        "domains": "查看知识领域",
        "recent": "查看最近更新",
        "sync": "同步语雀知识库",
        "rebuild": "重建知识索引",
        "delete": "删除知识",
    }.get(operation, "知识调用")


def summarize_response(operation: str, status: int, data: Any, outcome: str) -> str:
    if status >= 400 and isinstance(data, dict):
        detail = data.get("detail", data)
        if isinstance(detail, dict):
            return clean_text(
                str(detail.get("message") or detail.get("error") or f"HTTP {status}")
            )[:240]
        return "请求参数验证失败" if status == 422 else f"HTTP {status}"
    if isinstance(data, dict):
        if operation == "search":
            return f"命中 {data.get('count', len(data.get('results', [])))} 篇文档"
        if operation == "read" and data.get("title"):
            return clean_text(f"{data['title']} · {data.get('total_chars', 0)} 字")[
                :240
            ]
        if operation == "rules" and data.get("name"):
            return clean_text(
                f"{data['name']} · {len(data.get('checklist', []))} 项自查"
            )[:240]
        if operation == "stats" and "documents" in data:
            return f"知识库 {data['documents']} 篇文档"
        if operation == "submit_batch":
            return (
                f"成功 {data.get('count', 0)} 条，失败 {len(data.get('failed', []))} 条"
            )
        if operation == "sync":
            return f"新增 {data.get('created', 0)}，更新 {data.get('updated', 0)}，失败 {data.get('failed', 0)}"
        if data.get("action"):
            return clean_text(str(data["action"]) + " · " + str(data.get("title", "")))[
                :240
            ]
    return {
        "success": "调用成功",
        "partial": "部分成功",
        "failed": f"调用失败（HTTP {status}）",
    }[outcome]


class CallLogService:
    def __init__(self, db: Database, retention_days=30, max_entries=2000):
        self.db = db
        self.retention_days = max(1, min(365, retention_days))
        self.max_entries = max(1, min(100000, max_entries))

    @staticmethod
    def _scope(p: Principal) -> tuple[str, tuple]:
        if p.kind == "session" and p.user_id:
            return "user_id=?", (p.user_id,)
        return "credential_kind='key' AND key_prefix=?", (p.key_prefix,)

    def record(
        self,
        p: Principal,
        *,
        operation: str,
        method: str,
        path: str,
        client: str,
        status: int,
        duration_ms: float,
        request_data: Any,
        response_data: Any,
        request_truncated=False,
        response_truncated=False,
        outcome: str | None = None,
        ts: float | None = None,
    ):
        now = time.time() if ts is None else ts
        outcome = outcome or outcome_for(status, response_data)
        request_summary = summarize_request(operation, request_data)
        result_summary = summarize_response(operation, status, response_data, outcome)
        request_data, response_data = redact(request_data), redact(response_data)
        # Scope ownership is copied from the authenticated principal, never client input.
        with self.db.write() as conn:
            conn.execute(
                """INSERT INTO call_logs(user_id,key_prefix,credential_kind,credential_name,client,operation,method,path,status_code,outcome,duration_ms,request_summary,result_summary,request_json,response_json,request_truncated,response_truncated,ts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    p.user_id,
                    p.key_prefix,
                    p.kind,
                    clean_text(p.name)[:100],
                    client,
                    operation,
                    method,
                    clean_text(path)[:300],
                    status,
                    outcome,
                    round(duration_ms, 2),
                    request_summary,
                    result_summary,
                    json.dumps(request_data, ensure_ascii=False),
                    json.dumps(response_data, ensure_ascii=False),
                    int(request_truncated),
                    int(response_truncated),
                    now,
                ),
            )
            conn.execute(
                "DELETE FROM call_logs WHERE ts < ?",
                (now - self.retention_days * 86400,),
            )
            # Revoking a Key never removes its owner's historical records.
            clause, params = (
                ("user_id=?", (p.user_id,))
                if p.user_id
                else ("user_id IS NULL AND key_prefix=?", (p.key_prefix,))
            )
            conn.execute(
                f"DELETE FROM call_logs WHERE {clause} AND id NOT IN (SELECT id FROM call_logs WHERE {clause} ORDER BY ts DESC,id DESC LIMIT ?)",
                (*params, *params, self.max_entries),
            )

    def list(
        self,
        p: Principal,
        *,
        page=1,
        page_size=20,
        operation="",
        client="",
        outcome="",
        key_prefix="",
        query="",
        since: int | None = None,
        until: int | None = None,
    ) -> dict:
        clause, params = self._scope(p)
        where, values = (
            [clause, "ts>=?"],
            [*params, time.time() - self.retention_days * 86400],
        )
        for field, value in (
            ("operation", operation),
            ("client", client),
            ("outcome", outcome),
            ("key_prefix", key_prefix),
        ):
            if value:
                where.append(field + "=?")
                values.append(value)
        if since is not None:
            where.append("ts>=?")
            values.append(since)
        if until is not None:
            where.append("ts<?")
            values.append(until)
        if query:
            escaped = (
                query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            )
            where.append(
                "(request_summary LIKE ? ESCAPE '\\' OR result_summary LIKE ? ESCAPE '\\')"
            )
            values.extend(["%" + escaped + "%"] * 2)
        sql = " AND ".join(where)
        totals = self.db.one(
            f"SELECT COUNT(*) AS total, COALESCE(SUM(outcome='success'),0) AS success, COALESCE(SUM(outcome='partial'),0) AS partial, COALESCE(SUM(outcome='failed'),0) AS failed, COALESCE(AVG(duration_ms),0) AS avg_duration_ms FROM call_logs WHERE {sql}",
            tuple(values),
        )
        rows = self.db.query(
            f"SELECT id,key_prefix,credential_kind,credential_name,client,operation,method,path,status_code,outcome,duration_ms,request_summary,result_summary,request_truncated,response_truncated,ts FROM call_logs WHERE {sql} ORDER BY ts DESC,id DESC LIMIT ? OFFSET ?",
            (*values, page_size, (page - 1) * page_size),
        )
        # Filter options include revoked Keys that have historical entries.
        keys = self.db.query(
            f"SELECT DISTINCT key_prefix FROM call_logs WHERE {clause} AND ts>=? AND credential_kind='key' ORDER BY key_prefix",
            (*params, time.time() - self.retention_days * 86400),
        )
        return {
            "logs": [dict(row) for row in rows],
            "summary": {
                **dict(totals),
                "avg_duration_ms": round(totals["avg_duration_ms"], 2),
            },
            "page": page,
            "page_size": page_size,
            "total": totals["total"],
            "keys": [row["key_prefix"] for row in keys],
            "scope": "account" if p.kind == "session" else "key",
            "retention_days": self.retention_days,
            "max_entries": self.max_entries,
        }

    def get(self, p: Principal, log_id: int) -> dict | None:
        clause, params = self._scope(p)
        row = self.db.one(
            f"SELECT * FROM call_logs WHERE id=? AND {clause} AND ts>=?",
            (log_id, *params, time.time() - self.retention_days * 86400),
        )
        if not row:
            return None
        result = dict(row)
        result["request"] = json.loads(result.pop("request_json"))
        result["response"] = json.loads(result.pop("response_json"))
        return result
