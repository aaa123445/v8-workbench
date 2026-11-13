"""知识条目仓储层。

三件事在这里统一收口：
  1. 归一化：不同来源（语雀 / 管理员上传 / agent 提交）进来后统一成同一形状
  2. 元数据抽取：知识域、适用版本、标签 —— 这些决定 agent 能不能找对文档
  3. 变更审计：每次写入落一条 revision，支持回滚
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Iterable

from .db import Database
from .v8_categories import category_for_path

# 语雀目录树顶层 -> 归一化知识域。agent 检索时用 domain 过滤，必须稳定。
DOMAIN_ALIASES = {
    "开发准备": "开发准备",
    "开发文档": "开发文档",
    "开发规范": "开发规范",
    "扩展能力": "扩展能力",
    "BPM平台": "BPM平台",
    "UDC平台": "UDC平台",
    "集成平台": "集成平台",
    "门户平台": "门户平台",
    "移动端开发": "移动端开发",
    "业务组件": "业务组件",
    "V5V8融合": "V5V8融合",
    "数据迁移": "数据迁移",
    "文会事": "文会事",
    "开发调试": "开发调试",
    "服务与资源查询": "服务与资源查询",
    "真实案例库": "真实案例库",
    "线上问题总结": "线上问题总结",
    "复用工具": "复用工具",
}

# 从正文里抽"适用版本"。
#
# 这里必须严格：只认「适用版本」这个明确措辞，不能泛匹配「版本」。
# 语雀正文里有大量讲版本号命名规则的句子（"如当前版本：1.3.3，那么下一个
# 合理的版本号：1.3.4"），泛匹配会把这类举例当成平台适用版本，
# 一旦被 agent 当依据就会判断错版本兼容性。
_VERSION_RE = re.compile(
    r"适用版本[：:\s]*[vV]?(\d+\.\d+(?:\.\d+)?)\s*(以下|以上|之前|之后|起|及以下|及以上)?"
)
# 兜底：形如 "V8 3.18" / "V8版本 3.18"
_V8_VERSION_RE = re.compile(r"V8\s*(?:平台)?\s*版本?[：:\s]*[vV]?(\d+\.\d+)")
# 合理版本号范围。V8 当前是 3.x，历史上有 5.x 的公文模块，M5 客户端是 16.x；
# 超出这个范围的多半是误匹配
_PLAUSIBLE_MAJOR = {2, 3, 4, 5}

_QUALIFIER_MAP = {"起": "及以上", "之前": "以下", "之后": "及以上"}

_WS = re.compile(r"[ \t　]+")
_MULTI_NL = re.compile(r"\n{3,}")


@dataclass
class DocInput:
    id: str | None
    title: str
    body: str
    source: str
    path_text: str = ""
    summary: str = ""
    url: str = ""
    tags: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
    created_by: str = ""
    domain: str | None = None
    version_hint: str = ""
    is_deprecated: bool = False
    category_id: str = ""


@dataclass
class UpsertResult:
    doc_id: str
    action: str  # created | updated | unchanged
    title: str


class DocRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    # ---------------- 写入 ----------------

    def upsert(self, doc: DocInput) -> UpsertResult:
        doc_id = doc.id or _derive_id(doc.source, doc.title)
        body = _normalize_body(doc.body)
        if not body.strip():
            raise ValueError(f"文档正文为空，拒绝入库：{doc.title}")

        checksum = _checksum(doc.title, body, doc.path_text)
        now = time.time()
        domain = doc.domain or _infer_domain(doc.path_text)
        version = doc.version_hint or _infer_version(body, doc.path_text)
        tags = doc.tags or _infer_tags(doc.title, doc.path_text)
        summary = doc.summary or _summarize(body)
        words = _word_count(body)

        payload = {
            "title": doc.title,
            "path_text": doc.path_text,
            "domain": domain,
            "version_hint": version,
            "source": doc.source,
        }
        with self.db.write() as conn:
            existing = self.db.one(
                "SELECT checksum, body, title,category_id,knowledge_version FROM docs WHERE id = ?",
                (doc_id,),
            )
            if existing and existing["checksum"] == checksum:
                return UpsertResult(doc_id, "unchanged", doc.title)

            action = "updated" if existing else "created"
            conn.execute(
                """INSERT INTO docs (id, source, title, path_text, domain, body, summary, words,
                                     url, version_hint, tags, meta, checksum, created_by,
                                     created_at, updated_at, is_deprecated)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                       source=excluded.source,
                       title=excluded.title,
                       path_text=excluded.path_text,
                       domain=excluded.domain,
                       body=excluded.body,
                       summary=excluded.summary,
                       words=excluded.words,
                       url=excluded.url,
                       version_hint=excluded.version_hint,
                       tags=excluded.tags,
                       meta=excluded.meta,
                       checksum=excluded.checksum,
                       updated_at=excluded.updated_at,
                       is_deprecated=excluded.is_deprecated""",
                (
                    doc_id,
                    doc.source,
                    doc.title,
                    doc.path_text,
                    domain,
                    body,
                    summary,
                    words,
                    doc.url,
                    version,
                    json.dumps(tags, ensure_ascii=False),
                    json.dumps(doc.meta, ensure_ascii=False),
                    checksum,
                    doc.created_by,
                    now,
                    now,
                    1 if doc.is_deprecated else 0,
                ),
            )
            category = (
                doc.category_id
                or (existing["category_id"] if existing else None)
                or (
                    category_for_path(doc.path_text)
                    if doc.source == "yuque"
                    else "uncategorized"
                )
            )
            number = (existing["knowledge_version"] if existing else 0) + 1
            conn.execute(
                "UPDATE docs SET category_id=?,knowledge_version=? WHERE id=?",
                (category, number, doc_id),
            )
            conn.execute(
                "INSERT INTO knowledge_versions(doc_id,version,title,content,category_id,tags,summary,version_hint,url,actor,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    doc_id,
                    number,
                    doc.title,
                    body,
                    category,
                    json.dumps(tags, ensure_ascii=False),
                    summary,
                    version,
                    doc.url,
                    doc.created_by or "import",
                    now,
                ),
            )
            conn.execute(
                "INSERT OR REPLACE INTO doc_fts (id, text) VALUES (?, ?)",
                (doc_id, f"{doc.title}\n{doc.path_text}\n{body}"),
            )
            conn.execute(
                "INSERT INTO revisions (doc_id, action, actor, day_at, payload) VALUES (?,?,?,?,?)",
                (
                    doc_id,
                    action,
                    doc.created_by or "system",
                    now,
                    json.dumps(payload, ensure_ascii=False),
                ),
            )
        return UpsertResult(doc_id, action, doc.title)

    def bulk_upsert(self, docs: Iterable[DocInput]) -> dict[str, int]:
        stat = {"created": 0, "updated": 0, "unchanged": 0, "failed": 0}
        for d in docs:
            try:
                r = self.upsert(d)
                stat[r.action] += 1
            except Exception:
                stat["failed"] += 1
        return stat

    def deprecate(self, doc_id: str, actor: str) -> bool:
        with self.db.write() as conn:
            cur = conn.execute(
                "UPDATE docs SET is_deprecated = 1, updated_at = ? WHERE id = ?",
                (time.time(), doc_id),
            )
            if cur.rowcount:
                conn.execute(
                    "INSERT INTO revisions (doc_id, action, actor, day_at, payload) VALUES (?,?,?,?,?)",
                    (doc_id, "delete", actor, time.time(), "{}"),
                )
            return cur.rowcount > 0

    def delete(self, doc_id: str, actor: str) -> bool:
        with self.db.write() as conn:
            cur = conn.execute("DELETE FROM docs WHERE id = ?", (doc_id,))
            conn.execute("DELETE FROM doc_fts WHERE id = ?", (doc_id,))
            if cur.rowcount:
                conn.execute(
                    "INSERT INTO revisions (doc_id, action, actor, day_at, payload) VALUES (?,?,?,?,?)",
                    (doc_id, "delete", actor, time.time(), "{}"),
                )
            return cur.rowcount > 0

    # ---------------- 读取 ----------------

    def get(self, doc_id: str) -> dict | None:
        r = self.db.one("SELECT * FROM docs WHERE id = ?", (doc_id,))
        return _row_to_dict(r) if r else None

    def find_by_title(self, title: str) -> list[dict]:
        rows = self.db.query(
            "SELECT * FROM docs WHERE title = ? OR title LIKE ? ORDER BY length(title) LIMIT 10",
            (title, f"%{title}%"),
        )
        return [_row_to_dict(r) for r in rows]

    def refresh_derived(self, *, actor: str = "system") -> dict[str, int]:
        """重新推断所有文档的派生元数据（知识域/版本/标签/摘要/字数）。

        用途：当元数据推断逻辑本身改进后（比如版本号抽取变严格了），
        已入库文档的 checksum 没变，upsert 会直接返回 unchanged，
        旧的不准确元数据就永远留在库里。这个方法强制重算。

        只改派生字段，不动正文和 checksum，因此不会污染去重判断。
        """
        stat = {"total": 0, "changed": 0, "version_filled": 0}
        rows = self.db.query(
            "SELECT id, title, path_text, body, version_hint, tags FROM docs"
        )
        stat["total"] = len(rows)
        with self.db.write() as conn:
            for r in rows:
                domain = _infer_domain(r["path_text"] or "")
                version = _infer_version(r["body"] or "", r["path_text"] or "")
                tags = _infer_tags(r["title"] or "", r["path_text"] or "")
                summary = _summarize(r["body"] or "")
                words = _word_count(r["body"] or "")
                if version:
                    stat["version_filled"] += 1
                conn.execute(
                    """UPDATE docs SET domain=?, version_hint=?, tags=?, summary=?, words=?
                       WHERE id=?""",
                    (
                        domain,
                        version,
                        json.dumps(tags, ensure_ascii=False),
                        summary,
                        words,
                        r["id"],
                    ),
                )
                stat["changed"] += 1
        return stat

    def count_by_source(self) -> dict[str, int]:
        rows = self.db.query(
            "SELECT source, COUNT(*) AS n FROM docs WHERE is_deprecated=0 GROUP BY source"
        )
        return {r["source"]: r["n"] for r in rows}

    def list_docs(
        self, *, domain: str = "", source: str = "", limit: int = 100, offset: int = 0
    ) -> list[dict]:
        sql = "SELECT id, title, path_text, domain, source, words, version_hint, url, updated_at FROM docs WHERE is_deprecated=0"
        params: list[Any] = []
        if domain:
            sql += " AND (domain = ? OR domain LIKE ?)"
            params += [domain, f"{domain}%"]
        if source:
            sql += " AND source = ?"
            params.append(source)
        sql += " ORDER BY domain, path_text LIMIT ? OFFSET ?"
        params += [limit, offset]
        return [dict(r) for r in self.db.query(sql, tuple(params))]


# ---------------- 归一化与推断 ----------------


def _row_to_dict(r) -> dict:
    d = dict(r)
    try:
        d["tags"] = json.loads(d.get("tags") or "[]")
    except Exception:
        d["tags"] = []
    try:
        d["meta"] = json.loads(d.get("meta") or "{}")
    except Exception:
        d["meta"] = {}
    d["is_deprecated"] = bool(d.get("is_deprecated"))
    return d


def _derive_id(source: str, title: str) -> str:
    h = hashlib.sha1(f"{source}|{title}".encode("utf-8")).hexdigest()[:12]
    return f"{source}:{h}"


def _checksum(title: str, body: str, path_text: str) -> str:
    return hashlib.sha256(
        f"{title}\x00{path_text}\x00{body}".encode("utf-8")
    ).hexdigest()[:32]


def _normalize_body(body: str) -> str:
    b = body.replace("\r\n", "\n").replace("\r", "\n")
    b = _WS.sub(" ", b)
    b = _MULTI_NL.sub("\n\n", b)
    return b.strip()


def _word_count(body: str) -> int:
    cjk = len(re.findall(r"[一-鿿]", body))
    words = len(re.findall(r"[A-Za-z0-9_]+", body))
    return cjk + words


def _infer_domain(path_text: str) -> str:
    if not path_text:
        return "未分类"
    seg = path_text.split(" > ")
    top = seg[0].strip()
    return DOMAIN_ALIASES.get(top, top or "未分类")


def _infer_version(body: str, path_text: str) -> str:
    """抽取平台适用版本，保留上下界语义。

    只从正文前 3000 字里找，且只认「适用版本」明确措辞。

    关键：必须保留「以下/以上」这类限定词。原文写「适用版本：5.6以下版本」，
    如果只抽 "5.6"，agent 会理解成"5.6 及以上适用"，语义完全反了。
    宁可不抽，也不能抽成有歧义的值。

    输出形如 "5.6以下" / "3.18" / "3.15及以上"。
    """
    head = body[:3000]
    m = _VERSION_RE.search(head)
    if m:
        ver, qualifier = m.group(1), (m.group(2) or "")
        try:
            major = int(ver.split(".")[0])
        except ValueError:
            major = -1
        if 0 <= major <= 100:
            # 归一化限定词，"起" 和 "及以上" 同义
            q = _QUALIFIER_MAP.get(qualifier, qualifier)
            return f"{ver}{q}"
    # 兜底：V8 版本 3.18 这类写法，无上下界含义
    for m2 in _V8_VERSION_RE.finditer(head):
        ver = m2.group(1)
        try:
            major = int(ver.split(".")[0])
        except ValueError:
            continue
        if major in _PLAUSIBLE_MAJOR:
            return ver
    return ""


# 标签词典：命中即在标签里注册，让 agent 能用 tag 精确过滤
#
# 注意英文缩写的边界写法：这里必须用 (?![A-Za-z]) 而不是 \b。
# 因为中文也是 "word char"，"SPI扩展" 里 I 和 扩 之间没有 \b 边界，
# 用 \bSPI\b 会导致所有 "SPI扩展" 都抽不到标签。
_TAG_RULES: list[tuple[str, str]] = [
    (r"\bSPI(?![A-Za-z])", "SPI扩展"),
    (r"\bUDC(?![A-Za-z])", "UDC"),
    (r"\bBPM(?![A-Za-z])|流程按钮|流程触发", "BPM"),
    (r"组织同步", "组织同步"),
    (r"待办同步|事项中心", "待办同步"),
    (r"单点登录|\bSSO(?![A-Za-z])|免登", "单点登录"),
    (r"\bMQ(?![A-Za-z])|消息队列", "MQ"),
    (r"Nacos|注册中心|配置中心", "Nacos"),
    (r"Dubbo", "Dubbo"),
    (r"Mybatis|DynamicSQL", "Mybatis"),
    (r"缓存", "缓存"),
    (r"前端|组件|React|Vue|jssdk", "前端"),
    (r"移动端|M5|微协同|H5", "移动端"),
    (r"签章|E签宝|章管家", "签章"),
    (r"数据库|SQL|建表", "数据库"),
    (r"开放API|OpenAPI", "开放API"),
    (r"电子签章|发票|征信|OCR|电子档案", "三方能力"),
    (r"编码规范|命名|注释|代码格式", "编码规范"),
    (r"单元测试", "测试"),
    (r"国际化|多语言", "国际化"),
    (r"安全|加密|脱敏|鉴权", "安全"),
]


def _infer_tags(title: str, path_text: str) -> list[str]:
    hay = f"{path_text} {title}"
    out: list[str] = []
    for pat, tag in _TAG_RULES:
        if re.search(pat, hay, re.IGNORECASE):
            out.append(tag)
    return out


def _summarize(body: str, limit: int = 240) -> str:
    """抽前几段可读文字当摘要，跳过代码块和表格。"""
    lines: list[str] = []
    in_code = False
    for raw in body.split("\n"):
        ln = raw.strip()
        if ln.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not ln:
            continue
        if ln.startswith(("|", "!", "> 适用版本", "#")):
            continue
        if len(ln) < 8:
            continue
        lines.append(ln)
        if sum(len(x) for x in lines) >= limit:
            break
    text = " ".join(lines)
    return text[:limit]
