"""语雀抓取逻辑测试。

全部用本地 HTML 片段，不依赖网络 —— 这些测试要能在 CI 和离线环境跑，
而且语雀页面随时可能改版，真实网络测试会随机失败。
"""

from __future__ import annotations

import json
import sys
import urllib.parse
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.core import yuque  # noqa: E402


def _page(payload: dict) -> str:
    """构造语雀风格的页面：window.appData = JSON.parse(decodeURIComponent("..."))"""
    raw = json.dumps(payload, ensure_ascii=False)
    enc = urllib.parse.quote(raw, safe="")
    return (
        "<!DOCTYPE html><html><head><script>"
        f'window.appData = JSON.parse(decodeURIComponent("{enc}"));'
        "</script></head><body></body></html>"
    )


# ---------------- User-Agent ----------------

def test_user_agent_is_plain_browser():
    """UA 不能带自研后缀。

    语雀会检查 UA 里的浏览器标识，像 "...V8Workbench/0.1" 这种会被判定为爬虫，
    返回约 5KB 的空壳页（没有 appData）。这是线上真实踩过的坑。
    """
    ua = yuque.USER_AGENT
    assert "Mozilla/5.0" in ua
    assert "Chrome/" in ua
    assert "Safari/537.36" in ua
    for marker in ("V8Workbench", "python", "urllib", "curl"):
        assert marker.lower() not in ua.lower(), f"UA 不应包含 {marker}"


# ---------------- appData 解析 ----------------

def test_extract_app_data_roundtrip():
    page = _page({"book": {"id": 1, "toc": [{"title": "x"}]}})
    data = yuque._extract_app_data(page)
    assert data["book"]["id"] == 1


def test_extract_app_data_detects_antibot_shell():
    """被反爬拦截时要报"反爬"，不能误报"页面结构变化"。"""
    shell = "<html><body>Access denied V8Workbench</body></html>"
    with pytest.raises(yuque.YuqueError) as ei:
        yuque._extract_app_data(shell)
    msg = str(ei.value)
    assert "反爬" in msg or "空壳" in msg
    assert "结构变化" not in msg


def test_extract_app_data_reports_real_structure_change():
    """页面够大但没有 appData，才说明结构真的变了。"""
    big = "<html><body>" + "x" * 30000 + "</body></html>"
    with pytest.raises(yuque.YuqueError) as ei:
        yuque._extract_app_data(big)
    assert "结构变化" in str(ei.value)


def test_extract_app_data_fallback_object_literal():
    page = '<script>window.appData = {"book":{"id":9}};</script>'
    assert yuque._extract_app_data(page)["book"]["id"] == 9


# ---------------- TOC 还原 ----------------

def test_toc_to_nodes_builds_full_path():
    toc = [
        {"type": "TITLE", "title": "开发规范", "level": 0, "uuid": "a"},
        {"type": "TITLE", "title": "编码规范", "level": 1, "uuid": "b"},
        {"type": "DOC", "title": "命名风格", "level": 2, "uuid": "c",
         "url": "slug1", "id": 101},
        {"type": "DOC", "title": "前端开发规范", "level": 1, "uuid": "d",
         "url": "slug2", "id": 102},
    ]
    nodes = yuque._toc_to_nodes(toc)
    assert len(nodes) == 2
    assert nodes[0].path == ["开发规范", "编码规范", "命名风格"]
    assert nodes[1].path == ["开发规范", "前端开发规范"]
    assert nodes[0].doc_id == 101
    assert nodes[0].url == "slug1"


def test_toc_to_nodes_skips_title_nodes():
    toc = [
        {"type": "TITLE", "title": "目录项", "level": 0, "uuid": "a"},
        {"type": "DOC", "title": "文档", "level": 1, "uuid": "b", "url": "s", "id": 1},
    ]
    nodes = yuque._toc_to_nodes(toc)
    assert len(nodes) == 1
    assert nodes[0].title == "文档"


# ---------------- 正文抓取 ----------------

def test_fetch_doc_markdown_reads_content_field(monkeypatch):
    """正文在 data.content 里（Lake HTML），不是 body_lake。

    语雀把正文改成了异步加载，文档页 appData 里的 body_asl/body_lake 全为空，
    必须走 /api/docs/{slug}?book_id=… 接口。
    """
    lake = (
        '<p data-lake-id="1">组织同步逻辑</p>'
        '<h2>步骤</h2><ul><li>拉取</li></ul>'
    )
    payload = {"data": {"content": lake, "allow_public_api_read": True}}

    captured = {}

    def fake_fetch(url, **kw):
        captured["url"] = url
        captured["referer"] = kw.get("referer", "")
        return json.dumps(payload)

    monkeypatch.setattr(yuque, "_fetch", fake_fetch)

    node = yuque.TocNode(
        doc_id=1, uuid="u", title="组织同步", url="abc123", type="DOC",
        level=0, parent_uuid="", path=["组织同步"], updated_at="",
    )
    md = yuque.fetch_doc_markdown("seeyonkk/v8", node, book_id=62495446)

    assert "/api/docs/abc123" in captured["url"]
    assert "book_id=62495446" in captured["url"]
    assert "seeyonkk/v8/abc123" in captured["referer"]
    assert "组织同步逻辑" in md
    assert "步骤" in md


def test_fetch_doc_markdown_requires_book_id():
    node = yuque.TocNode(
        doc_id=1, uuid="u", title="t", url="s", type="DOC",
        level=0, parent_uuid="", path=[], updated_at="",
    )
    with pytest.raises(yuque.YuqueError, match="book_id"):
        yuque.fetch_doc_markdown("seeyonkk/v8", node, book_id=0)


def test_fetch_doc_markdown_empty_content(monkeypatch):
    monkeypatch.setattr(
        yuque, "_fetch",
        lambda url, **kw: json.dumps({"data": {"content": "", "allow_public_api_read": True}}),
    )
    node = yuque.TocNode(
        doc_id=1, uuid="u", title="空文档", url="s", type="DOC",
        level=0, parent_uuid="", path=[], updated_at="",
    )
    with pytest.raises(yuque.YuqueError, match="正文为空"):
        yuque.fetch_doc_markdown("seeyonkk/v8", node, book_id=1)


# ---------------- Lake -> Markdown ----------------

@pytest.mark.parametrize(
    ("lake", "expect"),
    [
        ("<p>普通段落</p>", "普通段落"),
        ("<h2>标题</h2>", "## 标题"),
        ("<ul><li>条目</li></ul>", "- 条目"),
        ("<strong>加粗</strong>", "**加粗**"),
        ("<code>inline</code>", "`inline`"),
        ("<pre>code line</pre>", "```"),
    ],
)
def test_lake_to_markdown(lake, expect):
    conv = yuque.LakeToMarkdown()
    conv.feed(lake)
    conv.close()
    assert expect in conv.markdown()


def test_lake_to_markdown_link():
    conv = yuque.LakeToMarkdown()
    conv.feed('<a href="https://example.com">链接</a>')
    conv.close()
    assert "[链接](https://example.com)" in conv.markdown()


def test_lake_to_markdown_skips_script():
    conv = yuque.LakeToMarkdown()
    conv.feed("<p>可见</p><script>var secret=1;</script>")
    conv.close()
    out = conv.markdown()
    assert "可见" in out
    assert "secret" not in out
