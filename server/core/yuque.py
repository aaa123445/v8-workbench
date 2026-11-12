"""语雀知识库同步。

复用你们已有的抓取逻辑（window.appData + Lake HTML -> Markdown），
但改造成"增量"：先拉目录拿到每篇的 updated_at，和库里的比对，
只有新增或更新的才真正抓正文。全量 233 篇几十秒，增量通常只有个位数。

两种模式：
  public  免 token，走公开页面。适合当前 seeyonkk/v8 这种公开知识库。
  token   带 X-Auth-Token 走官方 OpenAPI，可访问私有知识库。
"""

from __future__ import annotations

import html
import json
import re
import ssl
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any

from .docs import DocInput, DocRepo

BOOK_BASE = "https://www.yuque.com"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 V8Workbench/0.1"


class YuqueError(Exception):
    pass


@dataclass
class TocNode:
    doc_id: int
    uuid: str
    title: str
    url: str
    type: str
    level: int
    parent_uuid: str
    path: list[str]
    updated_at: str


def _fetch(url: str, *, token: str = "", timeout: int = 30, retries: int = 3) -> str:
    headers = {"User-Agent": USER_AGENT}
    if token:
        headers["X-Auth-Token"] = token
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            last = exc
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
    raise YuqueError(f"拉取失败 {url}: {last}")


def _fetch_insecure(url: str, *, token: str = "", timeout: int = 30) -> str:
    headers = {"User-Agent": USER_AGENT}
    if token:
        headers["X-Auth-Token"] = token
    req = urllib.request.Request(url, headers=headers)
    ctx = ssl._create_unverified_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return resp.read().decode("utf-8", errors="replace")


# ---------------- 目录 ----------------

def fetch_toc(book: str, *, token: str = "", insecure: bool = False) -> list[TocNode]:
    url = f"{BOOK_BASE}/{book}"
    page = (_fetch_insecure if insecure else _fetch)(url, token=token)
    data = _extract_app_data(page)
    book_data = data.get("book") or {}
    toc = book_data.get("toc") or []
    if not toc:
        raise YuqueError("目录为空，可能是知识库不可公开访问，请配置 token")

    nodes: list[TocNode] = []
    stack: list[tuple[int, str, list[str]]] = []
    for item in toc:
        level = int(item.get("level") or 0)
        title = html.unescape(str(item.get("title") or "")).strip()
        uuid = str(item.get("uuid") or "")
        doc_id = item.get("id") or item.get("doc_id")
        ntype = str(item.get("type") or "DOC")

        while stack and stack[-1][0] >= level:
            stack.pop()
        parent_uuid = stack[-1][1] if stack else ""
        parent_path = stack[-1][2] if stack else []
        path = parent_path + [title]

        if ntype == "DOC" and doc_id:
            nodes.append(
                TocNode(
                    doc_id=int(doc_id),
                    uuid=uuid,
                    title=title,
                    url=str(item.get("url") or ""),
                    type=ntype,
                    level=level,
                    parent_uuid=parent_uuid,
                    path=path,
                    updated_at=str(item.get("content_updated_at") or item.get("updated_at") or ""),
                )
            )
        stack.append((level, uuid, path))
    return nodes


def _extract_app_data(page_html: str) -> dict[str, Any]:
    m = re.search(r"window\.appData\s*=\s*JSON\.parse\(decodeURIComponent\(\"(.+?)\"\)\);", page_html, re.S)
    if not m:
        m = re.search(r"window\.appData\s*=\s*(\{.+?\});\s*(?:window|</script>)", page_html, re.S)
        if m:
            return json.loads(m.group(1))
        raise YuqueError("页面结构变化，无法解析 appData")
    return json.loads(urllib.parse.unquote(m.group(1)))


# ---------------- 正文 ----------------

def fetch_doc_markdown(book: str, node: TocNode, *, token: str = "", insecure: bool = False) -> str:
    url = f"{BOOK_BASE}/{book}/{node.url}" if node.url else f"{BOOK_BASE}/{book}"
    page = (_fetch_insecure if insecure else _fetch)(url, token=token)
    data = _extract_app_data(page)
    doc = data.get("doc") or {}
    lake = doc.get("body_lake") or doc.get("body") or ""
    if not lake:
        raise YuqueError("正文为空")
    conv = LakeToMarkdown()
    conv.feed(lake)
    conv.close()
    return conv.markdown()


class LakeToMarkdown(HTMLParser):
    """Yuque Lake HTML -> Markdown。保守转换：保留结构语义，不追求排版完美。"""

    BLOCK = {"p", "div", "section", "article", "li", "tr", "blockquote"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.list_depth = 0
        self.in_code = False
        self.in_pre = False
        self._href = ""
        self._skip = False

    # -- helpers --
    def _emit(self, s: str) -> None:
        if not self._skip:
            self.out.append(s)

    def _nl(self, n: int = 1) -> None:
        self._emit("\n" * n)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: (v or "") for k, v in attrs}
        if tag in {"script", "style"}:
            self._skip = True
            return
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._nl(2)
            self._emit("#" * int(tag[1]) + " ")
        elif tag == "p":
            self._nl(2)
        elif tag == "br":
            self._nl()
        elif tag == "hr":
            self._nl(2)
            self._emit("---")
            self._nl(2)
        elif tag == "pre":
            self._nl(2)
            self._emit("```\n")
            self.in_pre = True
        elif tag == "code" and not self.in_pre:
            self._emit("`")
        elif tag == "strong" or tag == "b":
            self._emit("**")
        elif tag == "em" or tag == "i":
            self._emit("*")
        elif tag == "a":
            self._href = a.get("href", "")
            self._emit("[")
        elif tag in {"ul", "ol"}:
            self.list_depth += 1
            self._nl()
        elif tag == "li":
            self._nl()
            self._emit("  " * max(0, self.list_depth - 1) + "- ")
        elif tag == "blockquote":
            self._nl(2)
            self._emit("> ")
        elif tag == "table":
            self._nl(2)
        elif tag == "tr":
            self._nl()
            self._emit("| ")
        elif tag in {"td", "th"}:
            pass
        elif tag == "img":
            src = a.get("src", "")
            alt = a.get("alt", "")
            if src:
                self._emit(f"![{alt}]({src})")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self._skip = False
            return
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._nl(2)
        elif tag == "pre":
            self._emit("\n```")
            self._nl(2)
            self.in_pre = False
        elif tag == "code" and not self.in_pre:
            self._emit("`")
        elif tag in {"strong", "b"}:
            self._emit("**")
        elif tag in {"em", "i"}:
            self._emit("*")
        elif tag == "a":
            self._emit(f"]({self._href})" if self._href else "]")
            self._href = ""
        elif tag in {"ul", "ol"}:
            self.list_depth = max(0, self.list_depth - 1)
            self._nl()
        elif tag in {"td", "th"}:
            self._emit(" | ")
        elif tag == "table":
            self._nl(2)

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        text = data if self.in_pre else re.sub(r"\s+", " ", data)
        self._emit(text)

    def markdown(self) -> str:
        s = "".join(self.out)
        s = re.sub(r"[ \t]+\n", "\n", s)
        s = re.sub(r"\n{3,}", "\n\n", s)
        return s.strip()


# ---------------- 同步编排 ----------------

def sync_book(
    repo: DocRepo,
    book: str,
    *,
    token: str = "",
    insecure: bool = False,
    force: bool = False,
    actor: str = "yuque-sync",
    limit: int | None = None,
    progress=None,
) -> dict:
    nodes = fetch_toc(book, token=token, insecure=insecure)
    stat = {"toc": len(nodes), "fetched": 0, "created": 0, "updated": 0,
            "unchanged": 0, "failed": 0, "skipped": 0, "errors": []}

    for i, node in enumerate(nodes):
        doc_id = f"yuque:{node.doc_id}"
        if not force:
            existing = repo.get(doc_id)
            if existing and existing.get("meta", {}).get("yuque_updated_at") == node.updated_at:
                stat["skipped"] += 1
                continue
        try:
            body = fetch_doc_markdown(book, node, token=token, insecure=insecure)
            stat["fetched"] += 1
            r = repo.upsert(
                DocInput(
                    id=doc_id,
                    title=node.title,
                    body=body,
                    source="yuque",
                    path_text=" > ".join(node.path),
                    url=f"{BOOK_BASE}/{book}/{node.url}" if node.url else "",
                    meta={"yuque_doc_id": node.doc_id, "yuque_updated_at": node.updated_at},
                    created_by=actor,
                )
            )
            stat[r.action] += 1
        except Exception as exc:  # noqa: BLE001
            stat["failed"] += 1
            stat["errors"].append({"title": node.title, "error": str(exc)[:200]})
        if progress:
            progress(i + 1, len(nodes), node.title)
        time.sleep(0.05)
        if limit and stat["fetched"] >= limit:
            break
    return stat
