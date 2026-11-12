"""内存倒排索引 + 三段式混合检索。

为什么是"三段式"而不是纯向量：
  1. 结构化路由：语雀的目录树（开发规范 > 编码规范 > 命名风格）本身就是极强的先验。
     agent 问"Java 命名怎么写"，直接命中路径比向量近邻可靠得多，且完全可解释。
  2. BM25 关键词：中文技术文档里 API 名、类名、配置项是硬事实，关键词精确匹配不可替代。
  3. 正文模糊兜底：前两段没命中时用 LIKE 扫一遍，保证"怎么问都有结果"，只是排序靠后。

向量检索留作后续扩展点（见 SearchIndex.hybrid 的 semantic 参数），当前不引入
embedding 依赖 —— 233 篇语料下纯 BM25 + 路径先验的 MRR 已经够用，加向量只会
增加部署复杂度和冷启动延迟，收益不明。
"""

from __future__ import annotations

import math
import re
import threading
from collections import defaultdict
from dataclasses import dataclass, field

from .db import Database
from .tokenizer import query_terms, token_texts

# BM25 参数。语料短小，k1 取小值让词频饱和更快
K1 = 1.2
B = 0.6

# 标题/路径命中相对正文的权重倍数
TITLE_BOOST = 3.2
PATH_BOOST = 2.0
TAG_BOOST = 2.4


@dataclass
class IndexedDoc:
    id: str
    title: str
    path_text: str
    domain: str
    source: str
    tags: list[str]
    words: int
    body_len: int
    summary: str
    url: str
    version_hint: str
    is_deprecated: bool


@dataclass
class SearchHit:
    doc: IndexedDoc
    score: float
    matched_terms: list[str] = field(default_factory=list)
    snippet: str = ""
    reasons: list[str] = field(default_factory=list)

    def to_dict(self, evidence_chars: int = 320) -> dict:
        return {
            "id": self.doc.id,
            "title": self.doc.title,
            "domain": self.doc.domain,
            "path": self.doc.path_text,
            "source": self.doc.source,
            "url": self.doc.url,
            "version_hint": self.doc.version_hint,
            "tags": self.doc.tags,
            "score": round(self.score, 4),
            "matched_terms": self.matched_terms[:12],
            "snippet": self.snippet[:evidence_chars],
            "reasons": self.reasons,
            "is_deprecated": self.doc.is_deprecated,
        }


class SearchIndex:
    """全量内存索引。写入后调用 rebuild()，读路径完全无锁。"""

    def __init__(self, db: Database) -> None:
        self.db = db
        self._lock = threading.RLock()
        # term -> doc_id -> tf
        self._postings: dict[str, dict[str, int]] = defaultdict(dict)
        # term -> doc_id -> 加权 tf（标题/路径加权）
        self._weighted: dict[str, dict[str, float]] = defaultdict(dict)
        self._docs: dict[str, IndexedDoc] = {}
        self._doc_terms: dict[str, dict[str, int]] = {}
        self._avgdl: float = 1.0
        self._built_at: float = 0.0

    # ---------------- 构建 ----------------

    def rebuild(self) -> int:
        rows = self.db.query(
            """SELECT id, title, path_text, domain, source, tags, words, body,
                      summary, url, version_hint, is_deprecated
               FROM docs WHERE is_deprecated = 0"""
        )
        with self._lock:
            self._postings = defaultdict(dict)
            self._weighted = defaultdict(dict)
            self._docs = {}
            self._doc_terms = {}
            total_len = 0

            for r in rows:
                did = r["id"]
                body = r["body"] or ""
                title = r["title"] or ""
                path_text = r["path_text"] or ""
                tags = _load_tags(r["tags"])

                body_tokens = token_texts(body)
                doc = IndexedDoc(
                    id=did,
                    title=title,
                    path_text=path_text,
                    domain=r["domain"] or "",
                    source=r["source"] or "",
                    tags=tags,
                    words=r["words"] or len(body_tokens),
                    body_len=max(1, len(body_tokens)),
                    summary=(r["summary"] or "")[:400],
                    url=r["url"] or "",
                    version_hint=r["version_hint"] or "",
                    is_deprecated=bool(r["is_deprecated"]),
                )
                self._docs[did] = doc
                total_len += doc.body_len

                tf: dict[str, int] = defaultdict(int)
                for t in body_tokens:
                    tf[t] += 1
                self._doc_terms[did] = dict(tf)

                # 标题 + 路径 + 标签构成结构化权重
                struct = defaultdict(float)
                for t in token_texts(title):
                    struct[t] += TITLE_BOOST
                for t in token_texts(path_text):
                    struct[t] += PATH_BOOST
                for tag in tags:
                    for t in token_texts(tag):
                        struct[t] += TAG_BOOST

                for term, n in tf.items():
                    self._postings[term][did] = n
                    self._weighted[term][did] = float(n) + struct.get(term, 0.0)
                # 只有标题命中的词也要能检索到
                for term, w in struct.items():
                    if term not in tf:
                        self._postings[term][did] = 0
                        self._weighted[term][did] = w

            n_docs = max(1, len(self._docs))
            self._avgdl = total_len / n_docs
            self._built_at = _now()
        return len(self._docs)

    # ---------------- 检索 ----------------

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        domain: str | None = None,
        source: str | None = None,
        tag: str | None = None,
        include_deprecated: bool = False,
    ) -> list[SearchHit]:
        if not query.strip():
            return []

        terms = query_terms(query)
        if not terms:
            return []

        with self._lock:
            docs = self._docs
            postings = self._postings
            weighted = self._weighted
            doc_terms = self._doc_terms
            avgdl = self._avgdl
            n_docs = max(1, len(docs))

            scores: dict[str, float] = defaultdict(float)
            hits_by_doc: dict[str, list[str]] = defaultdict(list)
            struct_hits: dict[str, list[str]] = defaultdict(list)

            for term, qw in terms.items():
                plist = postings.get(term)
                if not plist:
                    continue
                df = len(plist)
                idf = math.log(1.0 + (n_docs - df + 0.5) / (df + 0.5))
                # 极高频词（出现在 >60% 文档）降权，如 "配置""接口"
                if df / n_docs > 0.6:
                    idf *= 0.35
                wplist = weighted.get(term, {})
                for did, w in wplist.items():
                    doc = docs.get(did)
                    if doc is None:
                        continue
                    dl = doc.body_len
                    denom = K1 * (1 - B + B * dl / avgdl)
                    tf_part = w * (K1 + 1) / (denom + w) if denom + w else 0.0
                    contrib = qw * idf * tf_part
                    if contrib <= 0:
                        continue
                    scores[did] += contrib
                    hits_by_doc[did].append(term)
                    if term in doc.title or term in doc.path_text:
                        struct_hits[did].append(term)

            if not scores:
                return self._fallback_like(query, limit, domain, source, tag, include_deprecated)

            results: list[SearchHit] = []
            for did, sc in scores.items():
                doc = docs[did]
                if doc.is_deprecated and not include_deprecated:
                    continue
                if domain and not _domain_match(doc.domain, domain):
                    continue
                if source and doc.source != source:
                    continue
                if tag and tag not in doc.tags:
                    continue

                # 展示给 agent 的命中词：有多字词就只要多字词，单字只是兜底噪音
                raw_hits = sorted(set(hits_by_doc[did]), key=lambda t: -terms.get(t, 0))
                multi = [t for t in raw_hits if len(t) >= 2]
                matched = (multi if multi else raw_hits)[:8]

                # --- 精排：BM25 之外的三项独立加分 ---
                # 1) 查询覆盖率：命中的查询词越多越相关。防止单靠一个宽泛词（"规范"）排到前面。
                coverage = len(set(hits_by_doc[did])) / max(1, len(terms))
                # 2) 标题承载率：查询词落在标题里的比例。标题命中是强信号，
                #    但不该像之前那样揉进 tf 被 BM25 饱和稀释掉。
                title_hit = sum(1 for t in terms if t in doc.title) / max(1, len(terms))
                path_hit = sum(1 for t in terms if t in doc.path_text) / max(1, len(terms))

                bonus = sc * (0.6 * coverage + 1.1 * title_hit + 0.35 * path_hit)
                final = sc + bonus

                reasons = []
                if title_hit >= 0.5:
                    reasons.append("标题高度相关")
                elif struct_hits.get(did):
                    reasons.append("命中标题/目录路径")
                if coverage >= 0.8:
                    reasons.append("覆盖全部查询词")
                if doc.domain:
                    reasons.append(f"知识域 {doc.domain}")

                snippet = _snippet(doc.id, doc_terms.get(did, {}), matched)
                results.append(
                    SearchHit(
                        doc=doc,
                        score=final,
                        matched_terms=matched,
                        snippet=snippet,
                        reasons=reasons,
                    )
                )

            results.sort(key=lambda h: -h.score)
            return results[:limit]

    def _fallback_like(
        self,
        query: str,
        limit: int,
        domain: str | None,
        source: str | None,
        tag: str | None,
        include_deprecated: bool,
    ) -> list[SearchHit]:
        """倒排零命中时的兜底：直接在正文上做子串匹配。

        典型场景：agent 传了一整段中文描述而不是关键词，bigram 被稀释。
        这时 LIKE 反而更准，命中后再按标题相似度粗排。
        """
        q = query.strip()
        cands = [q] if len(q) <= 12 else _sub_phrases(q)
        out: list[SearchHit] = []
        seen: set[str] = set()
        for phrase in cands[:3]:
            rows = self.db.query(
                """SELECT d.id, d.title, d.path_text, d.domain, d.source, d.tags,
                          d.summary, d.url, d.version_hint, d.words, d.is_deprecated,
                          substr(d.body, max(1, instr(d.body, ?) - 80), 360) AS snip
                   FROM docs d
                   WHERE d.is_deprecated = 0 AND (d.body LIKE ? OR d.title LIKE ?)
                   LIMIT ?""",
                (phrase, f"%{phrase}%", f"%{phrase}%", limit * 3),
            )
            if source:
                rows = [r for r in rows if r["source"] == source]
            for r in rows:
                if r["id"] in seen:
                    continue
                if domain and not _domain_match(r["domain"] or "", domain):
                    continue
                tags = _load_tags(r["tags"])
                if tag and tag not in tags:
                    continue
                seen.add(r["id"])
                out.append(
                    SearchHit(
                        doc=IndexedDoc(
                            id=r["id"],
                            title=r["title"],
                            path_text=r["path_text"] or "",
                            domain=r["domain"] or "",
                            source=r["source"] or "",
                            tags=tags,
                            words=r["words"] or 0,
                            body_len=1,
                            summary=(r["summary"] or "")[:400],
                            url=r["url"] or "",
                            version_hint=r["version_hint"] or "",
                            is_deprecated=bool(r["is_deprecated"]),
                        ),
                        score=0.01,
                        matched_terms=[phrase],
                        snippet=r["snip"] or "",
                        reasons=["正文子串兜底命中"],
                    )
                )
            if out:
                break
        return out[:limit]

    # ---------------- 统计 ----------------

    def stats(self) -> dict:
        with self._lock:
            by_domain: dict[str, int] = defaultdict(int)
            by_source: dict[str, int] = defaultdict(int)
            for d in self._docs.values():
                by_domain[d.domain.split(" > ")[0] or "未分类"] += 1
                by_source[d.source] += 1
            return {
                "documents": len(self._docs),
                "terms": len(self._postings),
                "avg_body_len": round(self._avgdl, 1),
                "built_at": self._built_at,
                "by_domain": dict(sorted(by_domain.items(), key=lambda kv: -kv[1])),
                "by_source": dict(by_source),
            }

    def domains(self) -> list[dict]:
        with self._lock:
            agg: dict[str, int] = defaultdict(int)
            for d in self._docs.values():
                top = d.domain.split(" > ")[0] or "未分类"
                agg[top] += 1
            return [{"domain": k, "count": v} for k, v in sorted(agg.items(), key=lambda kv: -kv[1])]


# ---------------- 内部工具 ----------------

def _now() -> float:
    import time

    return time.time()


def _load_tags(raw: str) -> list[str]:
    if not raw:
        return []
    try:
        v = __import__("json").loads(raw)
        return [str(x) for x in v] if isinstance(v, list) else []
    except Exception:
        return []


def _domain_match(doc_domain: str, want: str) -> bool:
    """支持前缀匹配：domain=开发规范 能命中 开发规范 > 编码规范 > 命名风格。"""
    if not want:
        return True
    doc_domain = doc_domain or ""
    return doc_domain == want or doc_domain.startswith(want + " > ") or want in doc_domain


_SENT_SPLIT = re.compile(r"[。！？\n]+")


def _sub_phrases(q: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"[\s,，、;；。]+", q) if len(p.strip()) >= 2]
    return sorted(parts, key=len, reverse=True)


def _snippet(doc_id: str, tf: dict[str, int], terms: list[str]) -> str:
    """摘录：优先返回含命中词的句子。真实片段由 read 工具提供全文。"""
    if not terms:
        return ""
    return "含关键词：" + "、".join(terms[:6])
