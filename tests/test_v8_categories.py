from server.config import Settings
from server.core.container import Container
from server.core.docs import DocInput
from server.core.service import WorkbenchService
from server.core.v8_categories import initialize_v8_categories


def test_existing_v8_classification_preserves_bodies_versions_and_other_categories(
    tmp_path,
):
    c = Container(
        Settings(data_dir=tmp_path, bootstrap_admin_key="", yuque_enabled=False)
    )
    c.repo.upsert(
        DocInput(
            "v8-existing",
            "组织同步方案",
            "组织同步的完整步骤和验证要求。",
            "yuque",
            path_text="集成平台 > 组织同步",
            category_id="seeyon-v8",
        )
    )
    c.repo.upsert(
        DocInput(
            "v5-existing",
            "V5 示例",
            "原有 V5 文档内容保持完整。",
            "seeyon-v5",
            category_id="uncategorized",
        )
    )
    before = c.repo.get("v8-existing")
    with c.db.write() as conn:
        assert initialize_v8_categories(conn) == 1
    after = c.repo.get("v8-existing")
    assert after["category_id"] == "v8-integration"
    for field in [
        "id",
        "title",
        "body",
        "path_text",
        "updated_at",
        "knowledge_version",
    ]:
        assert after[field] == before[field]
    assert c.repo.get("v5-existing")["category_id"] == "uncategorized"
    c.knowledge.bootstrap()
    assert (
        c.db.scalar("SELECT count(*) FROM knowledge_audit WHERE action='v8_classify'")
        == 1
    )
    assert len(c.knowledge.versions("v8-existing")) == 1
    c.rebuild_index()
    svc = WorkbenchService(c)
    assert svc.search("组织同步", category_id="v8-integration")["count"] == 1
    assert svc.search("组织同步", category_id="seeyon-v8")["count"] == 1
    assert svc.search("组织同步", category_id="v8-udc")["count"] == 0


def test_new_sync_classifies_by_path_and_preserves_manual_choice(tmp_path):
    c = Container(
        Settings(data_dir=tmp_path, bootstrap_admin_key="", yuque_enabled=False)
    )
    c.repo.upsert(
        DocInput(
            "new",
            "自定义页面",
            "UDC 自定义页面的使用方法和验证步骤。",
            "yuque",
            path_text="UDC平台 > 自定义页面",
        )
    )
    assert c.repo.get("new")["category_id"] == "v8-udc"
    with c.db.write() as conn:
        conn.execute("UPDATE docs SET category_id='projects' WHERE id='new'")
    c.repo.upsert(
        DocInput(
            "new",
            "自定义页面",
            "UDC 自定义页面更新后的使用方法和验证步骤。",
            "yuque",
            path_text="UDC平台 > 自定义页面",
        )
    )
    c.knowledge.bootstrap()
    assert c.repo.get("new")["category_id"] == "projects"
