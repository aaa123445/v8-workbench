"""核心逻辑测试。不依赖网络和外部服务。

运行：.venv/bin/python -m pytest tests/ -v
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture()
def container():
    from server.config import Settings
    from server.core.container import Container

    d = tempfile.mkdtemp()
    s = Settings(
        data_dir=Path(d),
        require_auth=False,
        bootstrap_admin_key="",
    )
    return Container(s)


@pytest.fixture()
def svc(container):
    from server.core.service import WorkbenchService

    return WorkbenchService(container)


def _seed(container, **kw):
    from server.core.docs import DocInput

    base = dict(
        id=None,
        title="组织同步中间表扩展",
        body="组织同步中间表扩展用于把三方组织数据写入中间表，再由平台调度同步到正式组织表。",
        source="yuque",
        path_text="扩展能力 > 后端扩展 > SPI扩展 > 组织同步中间表扩展",
    )
    base.update(kw)
    return container.repo.upsert(DocInput(**base))


# ---------------- 分词 ----------------

def test_tokenizer_cjk_bigram():
    from server.core.tokenizer import token_texts

    toks = token_texts("组织同步")
    assert "组织" in toks
    assert "同步" in toks


def test_tokenizer_keeps_technical_abbrev():
    from server.core.tokenizer import token_texts

    toks = token_texts("SPI扩展和UDC组件")
    assert "spi" in toks
    assert "udc" in toks


def test_tokenizer_drops_stopword_single_chars():
    from server.core.tokenizer import token_texts

    toks = token_texts("的了和是")
    assert toks == []


# ---------------- 入库 ----------------

def test_upsert_creates_and_dedupes(container):
    r1 = _seed(container)
    assert r1.action == "created"
    r2 = _seed(container)  # 同内容
    assert r2.action == "unchanged"
    r3 = _seed(container, body="组织同步中间表扩展，补充：支持增量与全量两种模式。")
    assert r3.action == "updated"


def test_upsert_rejects_empty_body(container):
    from server.core.docs import DocInput

    with pytest.raises(ValueError):
        container.repo.upsert(DocInput(id=None, title="空", body="   ", source="agent"))


def test_domain_and_tags_inferred(container):
    r = _seed(container)
    doc = container.repo.get(r.doc_id)
    assert doc["domain"] == "扩展能力"
    assert "SPI扩展" in doc["tags"]
    assert "组织同步" in doc["tags"]


def test_version_hint_extracted(container):
    r = _seed(container, body="适用版本：3.18\n组织同步逻辑说明如下。")
    doc = container.repo.get(r.doc_id)
    assert doc["version_hint"] == "3.18"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("适用版本：5.6以下版本", "5.6以下"),
        ("适用版本：5.3以上版本", "5.3以上"),
        ("适用版本：3.15及以上版本", "3.15及以上"),
        ("适用版本：3.18", "3.18"),
        ("适用版本：5.6.0及以上版本", "5.6.0及以上"),
    ],
)
def test_version_qualifier_preserved(container, raw, expected):
    """上下界限定词必须保留。

    原文「适用版本：5.6以下版本」若只抽成 "5.6"，agent 会理解成
    「5.6 及以上适用」，语义完全反了 —— 这比不抽更危险。
    """
    r = _seed(container, body=f"{raw}\n正文说明。")
    assert container.repo.get(r.doc_id)["version_hint"] == expected


def test_version_ignores_version_number_examples(container):
    """讲版本号命名规则的句子不能被当成平台适用版本。"""
    body = "进行查证，使版本号有延续性。如当前版本：1.3.3，那么下一个合理的版本号：1.3.4。"
    r = _seed(container, body=body)
    assert container.repo.get(r.doc_id)["version_hint"] == ""


def test_refresh_derived_recomputes(container):
    """元数据推断逻辑改进后，老数据要能通过 refresh_derived 刷新。"""
    r = _seed(container, body="适用版本：3.18\n组织同步说明。")
    # 模拟旧的、不准确的派生数据
    with container.db.write() as conn:
        conn.execute(
            "UPDATE docs SET version_hint='9.9', tags='[]', domain='错误域' WHERE id=?",
            (r.doc_id,),
        )
    stat = container.repo.refresh_derived()
    assert stat["total"] >= 1
    doc = container.repo.get(r.doc_id)
    assert doc["version_hint"] == "3.18"
    assert doc["domain"] == "扩展能力"
    assert "SPI扩展" in doc["tags"]


def test_checksum_dedup_is_content_based(container):
    a = _seed(container, title="A", body="同样的正文内容，用于校验去重逻辑是否按内容判定。")
    b = _seed(container, title="A", body="同样的正文内容，用于校验去重逻辑是否按内容判定。")
    assert a.doc_id == b.doc_id
    assert b.action == "unchanged"


# ---------------- 检索 ----------------

def test_search_finds_by_title(container, svc):
    _seed(container)
    container.rebuild_index()
    out = svc.search("组织同步 中间表")
    assert out["count"] >= 1
    assert out["results"][0]["title"] == "组织同步中间表扩展"


def test_search_ranks_title_match_first(container, svc):
    from server.core.docs import DocInput

    container.repo.upsert(
        DocInput(
            id=None,
            title="命名风格",
            body="Java 命名风格：类名用大驼峰，方法用小驼峰，常量全大写。",
            source="yuque",
            path_text="开发规范 > 编码规范 > 命名风格",
        )
    )
    container.repo.upsert(
        DocInput(
            id=None,
            title="UDC接入规范",
            body="UDC 接入规范描述了接入流程和规范要求，规范要求较多。",
            source="yuque",
            path_text="开发规范 > UDC接入规范",
        )
    )
    container.rebuild_index()
    out = svc.search("命名规范")
    assert out["results"][0]["title"] == "命名风格"


def test_search_domain_filter(container, svc):
    from server.core.docs import DocInput

    _seed(container)
    container.repo.upsert(
        DocInput(
            id=None,
            title="前端开发规范",
            body="前端开发规范说明组件目录与依赖管理。",
            source="yuque",
            path_text="开发规范 > 前端开发规范",
        )
    )
    container.rebuild_index()
    out = svc.search("规范", domain="开发规范")
    assert all(r["domain"] == "开发规范" for r in out["results"])


def test_search_empty_query_raises(svc):
    from server.core.service import ServiceError

    with pytest.raises(ServiceError):
        svc.search("   ")


def test_search_fallback_on_phrase(container, svc):
    """倒排零命中时要走子串兜底，不能直接返回空。"""
    _seed(container, title="公文正文数据格式", body="这里描述正文数据结构与字段含义。",
          path_text="开发文档 > 公文正文数据格式介绍")
    container.rebuild_index()
    out = svc.search("正文数据结构")
    assert out["count"] >= 1


# ---------------- 规范 ----------------

def test_resolve_profile_by_key():
    from server.core.rules import resolve_profile

    assert resolve_profile("spi").key == "spi"
    assert resolve_profile("frontend").key == "frontend"


def test_resolve_profile_by_natural_language():
    from server.core.rules import resolve_profile

    assert resolve_profile("给客户做组织同步").key == "integration"
    assert resolve_profile("写个前端组件").key == "frontend"
    assert resolve_profile("完全无关的东西").key == "general"


def test_rules_returns_checklist(svc):
    out = svc.rules("spi")
    assert out["profile"] == "spi"
    assert len(out["checklist"]) > 0
    assert "SPI" in out["brief"] or "spi" in out["brief"]


def test_rules_resolves_doc_ids(container, svc):
    from server.core.docs import DocInput

    container.repo.upsert(
        DocInput(id=None, title="工程结构", body="工程结构说明：客开代码与平台代码物理隔离。",
                 source="yuque", path_text="开发规范 > 工程结构")
    )
    container.rebuild_index()
    out = svc.rules("spi")
    idx = {d["title"]: d for d in out["documents_index"]}
    assert "工程结构" in idx
    assert idx["工程结构"]["id"]


# ---------------- 读取 ----------------

def test_read_pagination(container, svc):
    from server.core.docs import DocInput

    # 用可区分的序列，否则相同字符重复会掩盖分页 bug
    body = "".join(f"第{i}段内容。" for i in range(400))
    r = container.repo.upsert(DocInput(id=None, title="长文", body=body, source="agent"))
    out = svc.read(r.doc_id, max_chars=100)
    assert out["truncated"] is True
    assert out["next_offset"] == 100
    out2 = svc.read(r.doc_id, max_chars=100, offset=100)
    assert out2["content"] != out["content"]
    assert out["content"] == body[:100]
    assert out2["content"] == body[100:200]


def test_read_by_title_ambiguous(container, svc):
    from server.core.docs import DocInput

    container.repo.upsert(DocInput(id=None, title="同名文档", body="第一个同名文档的正文内容。", source="agent"))
    container.repo.upsert(DocInput(id=None, title="同名文档", body="第二个同名文档的正文内容。", source="manual",
                                   path_text="另一个目录"))
    container.reindex = container.rebuild_index()
    container.rebuild_index()
    out = svc.read(title="同名文档")
    assert out.get("ambiguous") is True


# ---------------- 鉴权 ----------------

def test_auth_create_and_verify(container):
    raw, meta = container.auth.create_key("t", "reader")
    assert raw.startswith("wb_rd_")
    p = container.auth.authenticate(raw)
    assert p.role == "reader"
    assert p.can("reader") is True
    assert p.can("writer") is False


def test_auth_revoke(container):
    from server.core.auth import AuthError

    raw, meta = container.auth.create_key("t", "writer")
    assert container.auth.revoke(meta["prefix"]) is True
    with pytest.raises(AuthError):
        container.auth.authenticate(raw)


def test_auth_bad_key(container):
    from server.core.auth import AuthError

    with pytest.raises(AuthError):
        container.auth.authenticate("wb_rd_nonexistent")


def test_quota_daily_limit(container):
    from server.core.auth import QuotaExceeded

    raw, _ = container.auth.create_key("q", "reader", daily=2)
    p = container.auth.authenticate(raw)
    container.auth.check_quota(p)
    container.auth.log_usage(p, "search", True)
    container.auth.check_quota(p)
    container.auth.log_usage(p, "search", True)
    with pytest.raises(QuotaExceeded):
        container.auth.check_quota(p)


# ---------------- 端到端 ----------------

def test_contribute_then_searchable(container, svc):
    out = svc.submit_knowledge(
        title="UDC 自定义页面取当前用户为空",
        content="## 场景\nUDC 页面取不到当前用户。\n\n## 根因\n平台上下文未注入。\n\n## 解法\n等 ready 事件后再取。",
        actor="test",
        source="agent",
        tags=["UDC"],
    )
    assert out["action"] == "created"
    res = svc.search("UDC 当前用户为空")
    assert res["count"] >= 1
    assert res["results"][0]["id"] == out["id"]


def test_delete_removes_from_index(container, svc):
    r = _seed(container)
    container.rebuild_index()
    assert svc.search("组织同步中间表")["count"] == 1
    svc.delete_doc(r.doc_id, "test")
    assert svc.search("组织同步中间表")["count"] == 0
