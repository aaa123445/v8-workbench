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

# 必须是完整的浏览器 UA。
#
# 语雀会检查 UA 里的浏览器标识：带自研后缀（如 "...V8Workbench/0.1"）会被判定为
# 爬虫，返回一个约 5KB 的空壳页面（没有 window.appData）。这种情况下原实现会误报
# "页面结构变化"，实际是被反爬拦截了。这里务必保持标准 Chrome UA 的原样。
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# 空壳页面的特征：正常书籍页 100KB+，被拦截时只有几 KB
_MIN_PAGE_BYTES = 20000


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


def _headers(token: str = "", referer: str = "") -> dict[str, str]:
    h = {"User-Agent": USER_AGENT, "Accept": "text/html,application/json,*/*"}
    if token:
        h["X-Auth-Token"] = token
    if referer:
        h["Referer"] = referer
    return h


def _fetch(
    url: str,
    *,
    token: str = "",
    timeout: int = 30,
    retries: int = 3,
    referer: str = "",
    insecure: bool = False,
) -> str:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=_headers(token, referer))
            ctx = ssl._create_unverified_context() if insecure else ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            # 403/404 是确定性的，重试没意义
            if exc.code in (403, 404):
                raise YuqueError(f"语雀返回 {exc.code}：{url}") from exc
            last = exc
        except Exception as exc:  # noqa: BLE001
            last = exc
        if attempt < retries - 1:
            time.sleep(1.5 * (attempt + 1))
    raise YuqueError(f"拉取失败 {url}: {last}")


def _fetch_insecure(url: str, *, token: str = "", timeout: int = 30) -> str:
    return _fetch(url, token=token, timeout=timeout, retries=1, insecure=True)


# ---------------- 目录 ----------------

def fetch_book_meta(book: str, *, token: str = "", insecure: bool = False) -> tuple[int, list[dict]]:
    """返回 (book_id, toc 原始数组)。

    book_id 是抓正文必需参数，从书籍页的 appData.book.id 拿。
    """
    url = f"{BOOK_BASE}/{book}"
    page = (_fetch_insecure if insecure else _fetch)(url, token=token)
    data = _extract_app_data(page)
    book_data = data.get("book") or {}
    toc = book_data.get("toc") or []
    book_id = book_data.get("id")
    if not toc:
        raise YuqueError("目录为空，可能是知识库不可公开访问，请配置 token")
    if not book_id:
        raise YuqueError("未能从书籍页取到 book_id，语雀页面结构可能已变化")
    return int(book_id), toc


def fetch_toc(book: str, *, token: str = "", insecure: bool = False) -> list[TocNode]:
    _, toc = fetch_book_meta(book, token=token, insecure=insecure)
    return _toc_to_nodes(toc)


def _toc_to_nodes(toc: list[dict]) -> list[TocNode]:
    """把语雀的扁平 TOC 数组还原成带层级路径的节点列表。

    语雀的 toc 是扁平结构（每项带 level 和 parent_uuid），这里用栈还原出
    「开发规范 > 编码规范 > 命名风格」这样的完整路径 —— 这个路径是检索时
    结构化先验的来源，不能丢。
    """
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

        # 区分"被反爬拦截"和"页面结构真的变了"，否则排错方向完全是错的。
        # 正常书籍页 100KB+；被拦截时只有几 KB 且不含 appData。
        size = len(page_html.encode("utf-8", errors="ignore"))
        if size < _MIN_PAGE_BYTES:
            hint = ""
            if "V8Workbench" in page_html or "python" in page_html.lower():
                hint = "（检测到自定义 User-Agent，很可能是被反爬拦截）"
            raise YuqueError(
                f"语雀返回了 {size} 字节的空壳页面，疑似反爬拦截{hint}。"
                "请确认 USER_AGENT 是标准浏览器 UA；"
                "如知识库不公开，需设置 V8WB_YUQUE_TOKEN。"
            )
        raise YuqueError(
            f"页面结构变化，无法解析 appData（页面 {size} 字节）。"
            "语雀前端可能已改版，需要更新 server/core/yuque.py 的解析逻辑。"
        )
    return json.loads(urllib.parse.unquote(m.group(1)))


# ---------------- 正文 ----------------

def fetch_doc_markdown(
    book: str,
    node: TocNode,
    *,
    book_id: int,
    token: str = "",
    insecure: bool = False,
) -> str:
    """抓取单篇文档正文。

    正文不在文档页的 appData 里（body_asl/body_lake 均为空，语雀改成异步加载了），
    改走公开 API：/api/docs/{slug}?book_id={id}，正文在 data.content（Lake HTML）。

    这个接口要求 allow_public_api_read 为 true —— 公开知识库默认满足。
    """
    if not book_id:
        raise YuqueError("缺少 book_id，无法调用文档 API")

    api = f"{BOOK_BASE}/api/docs/{node.url}?book_id={book_id}"
    referer = f"{BOOK_BASE}/{book}/{node.url}" if node.url else f"{BOOK_BASE}/{book}"
    raw = (_fetch_insecure if insecure else _fetch)(
        api, token=token, referer=referer
    )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise YuqueError(f"文档 API 返回非 JSON：{raw[:120]}") from exc

    data = payload.get("data") or {}
    lake = data.get("content") or data.get("body") or data.get("body_lake") or ""
    if not lake:
        raise YuqueError(
            f"正文为空（allow_public_api_read={data.get('allow_public_api_read')}）"
        )
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
    book_id, toc = fetch_book_meta(book, token=token, insecure=insecure)
    nodes = _toc_to_nodes(toc)
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
            body = fetch_doc_markdown(
                book, node, book_id=book_id, token=token, insecure=insecure
            )
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
