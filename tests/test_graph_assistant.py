"""Tests for human-curated links, inferred citations, category suggestions and grounded Q&A."""

import json
import stat

import pytest
from fastapi.testclient import TestClient

from server.config import Settings
from server.core.container import Container
from server.core.docs import DocInput


@pytest.fixture
def env(tmp_path, monkeypatch):
    import server.api.http_app as mod

    c = Container(
        Settings(data_dir=tmp_path, require_auth=True, bootstrap_admin_key="")
    )
    monkeypatch.setattr(mod, "get_container", lambda: c)
    keys = {}
    for role in ["reader", "writer", "admin"]:
        key, _ = c.auth.create_key(role, role, rpm=10000, daily=100000)
        keys[role] = key

    def client(role):
        return TestClient(mod.app, headers={"Authorization": "Bearer " + keys[role]})

    return c, client, tmp_path


def add_doc(
    c,
    ident,
    title,
    category="backend",
    body="共享数据库处理方案的完整知识正文，说明复现步骤、实施方法和实际验证结果。",
):
    return c.repo.upsert(
        DocInput(
            id=ident,
            title=title,
            body=body,
            source="manual",
            category_id=category,
            path_text="技术开发 / 后端 / " + title,
            created_by="fixture",
        )
    )


def test_graph_bidirectional_manual_links_permissions_and_delete(env):
    c, client, _ = env
    add_doc(c, "guide:pool", "连接池异常排查")
    add_doc(c, "guide:tx", "事务回滚处理")
    writer, reader = client("writer"), client("reader")
    payload = {
        "source_id": "guide:pool",
        "target_id": "guide:tx",
        "kind": "solution",
        "note": "排障后执行",
    }
    assert reader.post("/api/v1/graph/links", json=payload).status_code == 403
    assert writer.post("/api/v1/graph/links", json=payload).status_code == 200
    left = reader.get("/api/v1/graph", params={"doc_id": "guide:pool"}).json()
    right = reader.get("/api/v1/graph", params={"doc_id": "guide:tx"}).json()
    assert left["edges"][0]["label"] == "问题与解法"
    assert left["edges"][0]["origin"] == "manual"
    assert right["edges"][0]["source_id"] == "guide:pool"
    ident = left["edges"][0]["id"]
    assert reader.delete("/api/v1/graph/links/" + ident).status_code == 403
    assert writer.delete("/api/v1/graph/links/" + ident).json() == {"deleted": True}
    assert (
        client("reader").get("/api/v1/graph", params={"doc_id": "missing"}).status_code
        == 404
    )
    assert (
        c.db.scalar("SELECT count(*) FROM knowledge_audit WHERE action='link_delete'")
        == 1
    )


def test_graph_detects_obsidian_links_and_site_document_links(env):
    c, client, _ = env
    add_doc(
        c,
        "note:wiki",
        "部署方案",
        body="先阅读 [[容量规划]] 和 [[note:容量]]，再继续。",
    )
    add_doc(c, "note:容量", "容量规划")
    add_doc(
        c,
        "note:router",
        "反向代理配置",
        body="参考 [部署方案](/#/documents/note%3Awiki)。",
    )
    wiki = client("reader").get("/api/v1/graph", params={"doc_id": "note:wiki"}).json()
    assert {e["origin"] for e in wiki["edges"]} == {"reference"}
    assert len(wiki["edges"]) == 2
    assert any(e["target_id"] == "note:容量" for e in wiki["edges"])
    cited = (
        client("reader").get("/api/v1/graph", params={"doc_id": "note:router"}).json()
    )
    assert cited["edges"][0]["target_id"] == "note:wiki"


def test_category_suggestions_are_explanatory_and_never_move_documents(env):
    c, client, _ = env
    add_doc(
        c,
        "v8:ext",
        "V8 SPI 扩展实现",
        category="v8-extensions",
        body="致远 V8 SPI 扩展开发实现方案，采用注册机制和接口实现，并包含项目验证方法与失败排查。",
    )
    add_doc(
        c,
        "web:css",
        "网页布局样式",
        category="frontend",
        body="前端页面 CSS 网格布局和响应式样式，实现网站适配并验证移动端页面。",
    )
    before = c.repo.get("v8:ext")["category_id"]
    out = client("writer").post(
        "/api/v1/classify", json={"title": "V8 SPI 插件", "content": "V8 扩展开发"}
    )
    assert out.status_code == 200
    assert out.json()["method"] == "retrieval"
    assert out.json()["suggestions"][0]["category_id"] == "v8-extensions"
    assert out.json()["suggestions"][0]["examples"]
    assert out.json()["automatic_move"] is False
    assert c.repo.get("v8:ext")["category_id"] == before
    assert (
        client("reader").post("/api/v1/classify", json={"title": "CSS"}).status_code
        == 200
    )


def test_scenario_detection_and_explicit_selection():
    from server.core.graph import scenario_for

    assert scenario_for("组织同步接口失败，怎么排查？") == "troubleshoot"
    assert scenario_for("V5 和 V8 的对比") == "compare"
    assert scenario_for("移动平台开发怎么入门？") == "learn"
    assert scenario_for("一般问题", "develop") == "develop"


def test_admin_model_settings_secret_protection_and_url_validation(env):
    c, client, data = env
    reader, writer, admin = client("reader"), client("writer"), client("admin")
    assert reader.get("/api/v1/admin/assistant").status_code == 403
    assert (
        writer.put(
            "/api/v1/admin/assistant",
            json={
                "enabled": True,
                "base_url": "https://api.example/v1",
                "model": "example",
                "api_key": "secret",
            },
        ).status_code
        == 403
    )
    invalid = admin.put(
        "/api/v1/admin/assistant",
        json={
            "enabled": True,
            "base_url": "ftp://provider.example/v1",
            "model": "x",
            "api_key": "s",
        },
    )
    assert invalid.status_code == 400
    saved = admin.put(
        "/api/v1/admin/assistant",
        json={
            "enabled": True,
            "base_url": "https://api.example/v1",
            "model": "example-model",
            "api_key": "model-secret-123456",
        },
    )
    assert saved.status_code == 200 and saved.json()["ready"]
    assert "api_key" not in saved.json()
    assert "model-secret" not in json.dumps(admin.get("/api/v1/admin/assistant").json())
    path = data / "agent-settings.json"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    raw = json.loads(path.read_text())
    assert raw["api_key"] == "model-secret-123456"
    assert (
        admin.put(
            "/api/v1/admin/assistant",
            json={
                "enabled": False,
                "base_url": "https://api.example/v1",
                "model": "example-model",
                "clear_key": True,
            },
        ).status_code
        == 200
    )
    assert not path.exists() or not json.loads(path.read_text()).get("api_key")


class FakeResponse:
    status_code = 200

    def __init__(self, body):
        self.body = body

    def json(self):
        return {"choices": [{"message": {"content": self.body}}]}


class FakeClient:
    answer = "先检查任务状态和重试队列[1]，再确认服务部署配置[2]。"
    request = None

    def __init__(self, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def post(self, url, **kwargs):
        FakeClient.request = (url, kwargs)
        return FakeResponse(FakeClient.answer)


def test_cloud_assistant_uses_relevant_evidence_chain_and_citations(env, monkeypatch):
    import httpx

    c, client, _ = env
    add_doc(
        c,
        "kb:queue",
        "任务重试队列",
        body="项目任务遇到连接失败时，先检查重试队列和退避策略，再检查服务地址。适用 V8 3.20。",
    )
    add_doc(
        c,
        "kb:deploy",
        "服务部署配置",
        body="验证服务部署配置和系统运行日志，通过健康检查确认服务启动情况。限制为 Linux systemd。",
    )
    c.assistant = __import__(
        "server.core.assistant", fromlist=["AssistantService"]
    ).AssistantService(c)
    c.assistant.save(
        True, "https://api.example/v1", "example-model", "server-model-key-98765"
    )
    monkeypatch.setattr(
        FakeClient, "answer", "先检查任务状态和重试队列[1]，再确认服务部署配置[2]。"
    )
    monkeypatch.setattr(httpx, "Client", FakeClient)
    c.repo.upsert(
        DocInput(
            id="kb:queue",
            title="任务重试队列",
            body="项目任务遇到连接失败时，先检查重试队列和退避策略，再检查服务地址。适用 V8 3.20。",
            source="manual",
            category_id="backend",
            created_by="fixture",
        )
    )
    with c.db.write() as conn:
        conn.execute(
            "INSERT INTO knowledge_links(id,source_id,target_id,kind,note,actor,created_at) VALUES (?,?,?,?,?,?,?)",
            ("edge-a", "kb:queue", "kb:deploy", "solution", "检查后阅读", "fixture", 1),
        )
    c.rebuild_index()
    response = client("reader").post(
        "/api/v1/assistant/ask",
        json={"question": "任务连接失败怎么排查？", "mode": "chain"},
    )
    assert response.status_code == 200, response.text
    out = response.json()
    assert out["status"] == "answered" and out["mode"] == "chain"
    assert len(out["citations"]) == 2 and len(out["chain"]) == 1
    assert "server-model-key" not in json.dumps(FakeClient.request[1]["json"])
    assert FakeClient.request[0] == "https://api.example/v1/chat/completions"
    assert "任务重试队列" in FakeClient.request[1]["json"]["messages"][1]["content"]
    monkeypatch.setattr(FakeClient, "answer", "未查到依据。")
    unsupported = (
        client("reader")
        .post(
            "/api/v1/assistant/ask",
            json={"question": "任务连接失败怎么排查？", "mode": "search"},
        )
        .json()
    )
    assert unsupported["status"] == "unsupported"
    assert "未采纳" in unsupported["answer"]
    assert (
        c.db.scalar("SELECT count(*) FROM call_logs WHERE path='/api/v1/assistant/ask'")
        == 2
    )


def test_cloud_assistant_disabled_and_empty_evidence(env):
    _, client, _ = env
    assert (
        client("reader")
        .post("/api/v1/assistant/ask", json={"question": "如何解决未知量子模块故障？"})
        .status_code
        == 503
    )


def test_graph_excludes_drafts_deprecated_and_code_examples(env):
    c, client, _ = env
    add_doc(
        c,
        "pub:a",
        "发布知识",
        body="```md\n[[内部草稿]]\n[[pub:b]]\n```\n\n正文参考 [[pub:b]]。",
    )
    add_doc(c, "pub:b", "发布关联")
    add_doc(c, "pub:old", "已下架", body="[[pub:a]]")
    c.repo.deprecate("pub:old", "test")
    out = client("reader").get("/api/v1/graph", params={"doc_id": "pub:a"}).json()
    assert {n["id"] for n in out["nodes"]} == {"pub:a", "pub:b"}
    assert len(out["edges"]) == 1
    assert (
        client("reader").get("/api/v1/graph", params={"doc_id": "pub:old"}).status_code
        == 404
    )


def test_graph_mutation_owner_and_category_boundary(env):
    from server.core.graph import GraphService

    c, client, _ = env
    add_doc(c, "back:a", "后端事务", category="backend")
    add_doc(c, "front:a", "前端表单", category="frontend")
    raw, _ = c.auth.create_key("other writer", "writer", rpm=1000, daily=1000)
    other = c.auth.authenticate(raw)
    link = GraphService(c).save(other, "back:a", "front:a", "related")
    assert (
        client("writer").delete("/api/v1/graph/links/" + link["id"]).status_code == 403
    )
    limited = (
        client("reader")
        .get("/api/v1/graph", params={"doc_id": "back:a", "category_id": "backend"})
        .json()
    )
    assert {n["id"] for n in limited["nodes"]} == {"back:a"}
    assert not limited["edges"]
    assert (
        client("admin").delete("/api/v1/graph/links/" + link["id"]).status_code == 200
    )


def test_platform_comparison_keeps_both_platforms_and_no_evidence_never_calls_provider(
    env, monkeypatch
):
    from server.core.assistant import platform_scope

    c, client, _ = env
    assert platform_scope("V5 与 V8 的区别") == ""
    assert platform_scope("致远V8扩展接口") == "seeyon-v8"
    c.assistant.save(
        True, "https://api.example/v1", "example-model", "test-only-secret"
    )

    def no_network(*args, **kwargs):
        raise AssertionError("No evidence must not contact the provider")

    monkeypatch.setattr("httpx.Client.post", no_network)
    result = c.assistant.ask("不存在的量子模块")
    assert result["status"] == "no_evidence"
    assert result["citations"] == []


def test_learning_order_prioritizes_prerequisites(env):
    from server.core.graph import GraphService

    c, client, _ = env
    add_doc(c, "advanced", "高级方案")
    add_doc(c, "basic", "前置基础")
    p = c.auth.authenticate(client("writer").headers["Authorization"].split()[-1])
    GraphService(c).save(p, "advanced", "basic", "prerequisite")
    result = (
        client("reader")
        .get("/api/v1/graph", params={"doc_id": "advanced", "scenario": "learn"})
        .json()
    )
    assert [n["id"] for n in result["reading_order"]] == ["basic", "advanced"]


def test_global_graph_collects_disconnected_chains_and_excludes_unlinked_docs(env):
    c, client, _ = env
    add_doc(c, "first", "第一组引用", body="文档参考 [[second]]。")
    add_doc(c, "second", "第一组目标")
    add_doc(c, "third", "第二组引用", category="frontend", body="文档参考 [[fourth]]。")
    add_doc(c, "fourth", "第二组目标", category="frontend")
    add_doc(c, "unlinked", "无关但标题相似的第一组知识")
    result = client("reader").get("/api/v1/graph/all")
    assert result.status_code == 200
    data = result.json()
    assert {n["id"] for n in data["nodes"]} == {"first", "second", "third", "fourth"}
    assert len(data["edges"]) == 2
    assert all(e["origin"] == "reference" for e in data["edges"])
    subset = client("reader").get("/api/v1/graph/all?category_id=backend").json()
    assert {n["id"] for n in subset["nodes"]} == {"first", "second"}
    assert len(subset["edges"]) == 1


def test_global_graph_empty_database_has_no_synthetic_edges(env):
    c, client, _ = env
    add_doc(c, "standalone", "独立知识")
    result = client("reader").get("/api/v1/graph/all").json()
    assert result["nodes"] == [] and result["edges"] == []


def test_assistant_allows_remote_http_and_forwards_followup_history(env, monkeypatch):
    c, client, _ = env
    add_doc(c, "kb:pool", "连接池排查", body="连接池故障先检查状态和服务日志。")
    c.rebuild_index()
    c.assistant.save(True, "http://provider.example:8080/v1", "test-model", "test-secret")
    monkeypatch.setattr("httpx.Client", FakeClient)
    monkeypatch.setattr(FakeClient, "answer", "检查连接池状态[1]。")
    response = client("reader").post("/api/v1/assistant/ask", json={
        "question": "接下来呢？", "history": [{"role": "user", "content": "连接池故障怎么排查？"}, {"role": "assistant", "content": "先检查状态"}]
    })
    assert response.status_code == 200
    assert response.json()["status"] == "answered"
    assert FakeClient.request[0] == "http://provider.example:8080/v1/chat/completions"
    messages = FakeClient.request[1]["json"]["messages"]
    assert messages[1]["content"] == "连接池故障怎么排查？"
    assert messages[2]["role"] == "assistant"
    assert client("reader").post("/api/v1/assistant/ask", json={"question":"测试问题", "history":[{"role":"system", "content":"bad"}]}).status_code == 422


def test_provider_denial_preserves_actionable_error_and_redacts_secret(env, monkeypatch):
    from server.core.knowledge import KnowledgeError
    c, _, _ = env
    add_doc(c, "kb:pool", "连接池排查", body="连接池故障先检查状态。")
    c.rebuild_index()
    c.assistant.save(True, "https://provider.example/v1", "test-model", "sensitive-test-secret")
    class DeniedResponse:
        status_code = 403
        def json(self):
            return {"error": {"message": "geographic location blocked sensitive-test-secret"}}
    monkeypatch.setattr(FakeClient, "post", lambda *a, **kw: DeniedResponse())
    monkeypatch.setattr("httpx.Client", FakeClient)
    with pytest.raises(KnowledgeError) as exc:
        c.assistant.ask("连接池故障排查")
    assert "403" in str(exc.value) and "geographic" in str(exc.value)
    assert "sensitive-test-secret" not in str(exc.value)


def test_reasoning_model_has_enough_output_budget_and_reports_exhaustion(env, monkeypatch):
    from server.core.knowledge import KnowledgeError
    c, _, _ = env
    add_doc(c, "kb:pool", "连接池排查", body="连接池故障先检查状态。")
    c.rebuild_index()
    c.assistant.save(True, "https://provider.example/v1", "reasoner", "test-secret")
    class ExhaustedResponse:
        status_code = 200
        def json(self):
            return {"choices": [{"finish_reason": "length", "message": {"role": "assistant", "content": None}}]}
    def response(self, url, **kwargs):
        assert kwargs["json"]["max_tokens"] >= 8192
        return ExhaustedResponse()
    monkeypatch.setattr(FakeClient, "post", response)
    monkeypatch.setattr("httpx.Client", FakeClient)
    with pytest.raises(KnowledgeError, match="输出额度"):
        c.assistant.ask("连接池故障排查")
