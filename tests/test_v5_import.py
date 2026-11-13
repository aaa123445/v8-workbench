import pytest
from ingest.import_v5 import parse_corpus, import_corpus, SITES
from server.config import Settings
from server.core.container import Container
from server.core.service import WorkbenchService


def corpus(tmp_path):
    folder = tmp_path / "resources/docs"
    folder.mkdir(parents=True)
    for site in SITES:
        text = "- 提取文档数：1\n\n## 1. 事务处理\n\n> 原始路径：`/tx.html`  \n> 相对路径：`tx.md`\n\n## 使用说明\n\n事务失败后回滚并释放连接，这是可复用的方案。\n\n[相关说明](next.html)\n"
        if site == "cmpdev":
            text = "- 提取文档数：1\n\n## 1. 移动端组件\n\n> 路由：`mobile`  \n> 版本：``  \n> Markdown URL：https://open.seeyoncloud.com/cmpdev/mobile.md\n\n移动端组件的完整调用方式与版本说明。"
        (folder / f"{site}_文档汇总.md").write_text(text)
    return tmp_path


def test_v5_split_categories_isolation_and_idempotence(tmp_path):
    root = corpus(tmp_path / "corpus")
    docs, report = parse_corpus(root, "test-commit")
    assert len(docs) == 9 and report["by_site"]["v5devCTP"] == 1
    assert "https://open.seeyoncloud.com/v5devCTP/next.html" in docs[0].body
    c = Container(
        Settings(
            data_dir=tmp_path / "data", bootstrap_admin_key="", yuque_enabled=False
        )
    )
    assert import_corpus(c, docs) == {"created": 9}
    assert import_corpus(c, docs) == {"unchanged": 9}
    assert c.db.scalar("SELECT count(*) FROM knowledge_versions") == 9
    c.rebuild_index()
    svc = WorkbenchService(c)
    assert svc.search("事务", category_id="seeyon-v5")["count"] > 0
    assert svc.search("事务", category_id="seeyon-v8")["count"] == 0
    doc = c.repo.get(docs[0].id)
    assert (
        doc["category_id"] == "v5-v5devctp"
        and doc["meta"]["origin_revision"] == "test-commit"
    )


def test_mismatched_corpus_stops_before_import(tmp_path):
    root = corpus(tmp_path)
    file = root / "resources/docs/v5devCTP_文档汇总.md"
    file.write_text(file.read_text().replace("文档数：1", "文档数：2"))
    with pytest.raises(ValueError, match="count"):
        parse_corpus(root)


def test_fetch_failure_is_skipped_or_replaced_with_verified_snapshot(tmp_path):
    root = corpus(tmp_path)
    file = root / "resources/docs/cmpdev_文档汇总.md"
    file.write_text(file.read_text().replace(
        "移动端组件的完整调用方式与版本说明。",
        "## 资源\n\n（未能获取 Markdown：HTTP 404，URL：https://example.com/sources.md）",
    ))
    docs, report = parse_corpus(root)
    assert len(docs) == 8
    assert report["fetch_failed_skipped"] == 1
    url = "https://open.seeyoncloud.com/cmpdev/#/sources"
    snapshot = {"mobile": {"url": url, "body": "# 资源下载\n\n[Android Studio](https://developer.android.google.cn/studio)", "sources": [url]}}
    recovered, report = parse_corpus(root, cmp_snapshot=snapshot)
    assert report["fetch_recovered"] == 1
    cmp_doc = next(d for d in recovered if d.meta["site"] == "cmpdev")
    assert cmp_doc.url == url and "Android Studio" in cmp_doc.body
    assert cmp_doc.meta["capture_sources"] == [url]
    snapshot["mobile"]["body"] = "（未能获取 Markdown：HTTP 404）"
    with pytest.raises(ValueError, match="fetch failure"):
        parse_corpus(root, cmp_snapshot=snapshot)
