import json

import pytest
from fastapi.testclient import TestClient

from server.config import Settings
from server.core.container import Container
from server.core.docs import DocInput
from server.core.knowledge import KnowledgeError
from server.core.service import WorkbenchService


@pytest.fixture
def env(tmp_path, monkeypatch):
    import server.api.http_app as mod

    c = Container(
        Settings(data_dir=tmp_path, require_auth=True, bootstrap_admin_key="")
    )
    monkeypatch.setattr(mod, "get_container", lambda: c)
    keys = {}
    people = {}
    for role in ["reader", "writer", "admin"]:
        raw, _ = c.auth.create_key(role, role, rpm=10000, daily=100000)
        keys[role] = raw
        people[role] = c.auth.authenticate(raw)
    other, _ = c.auth.create_key("other", "writer", rpm=10000, daily=100000)
    keys["other"] = other
    people["other"] = c.auth.authenticate(other)

    def client(who):
        return TestClient(mod.app, headers={"Authorization": "Bearer " + keys[who]})

    return c, people, client


def payload(**kw):
    return dict(
        title="Production connection pool exhausted",
        content="Connections are retained by failed transactions. Use explicit context management, rollback on exceptions, and verify the pool returns to baseline after concurrent failures.",
        category_id="backend",
        tags=["database"],
        summary="Avoid leaking connections",
        source="agent",
        problem="Failed transactions leak connections after exceptions.",
        solution="Use scoped transactions with rollback on failure and close each connection after use.",
        verification="A concurrency test with 100 failed transactions returns to the baseline pool count.",
        limitations="Verified on PostgreSQL 16 only.",
        verified=True,
        reusable=True,
        **kw,
    )


def test_review_visibility_ownership_versions_and_conflict(env):
    c, p, client = env
    k = c.knowledge
    svc = WorkbenchService(c)
    draft = k.propose(p["writer"], payload(), False)
    assert draft["status"] == "draft" and not svc.search("connection")["results"]
    assert (
        client("other").get("/api/v1/contributions/" + draft["id"]).status_code == 404
    )
    assert client("writer").get("/api/v1/contributions?review=true").status_code == 403
    pending = k.propose(p["writer"], payload(), True, draft["id"])
    assert pending["status"] == "pending"
    assert k.propose(p["writer"], payload())["id"] == pending["id"]
    assert (
        client("writer")
        .post(
            "/api/v1/contributions/" + pending["id"] + "/review",
            json={"action": "publish"},
        )
        .status_code
        == 403
    )
    published = k.review(p["admin"], pending["id"], "publish", "Verified")
    did = published["published_doc_id"]
    assert svc.read(did)["knowledge_version"] == 1
    assert svc.search("connection", category_id="technology")["count"] == 1
    assert svc.search("connection", category_id="frontend")["count"] == 0
    assert k.browse("technology")["total"] == 1
    update = {
        **payload(),
        "target_doc_id": did,
        "base_version": 1,
        "content": payload()["content"] + " Improved handling.",
    }
    a = k.propose(p["writer"], update)
    b = k.propose(
        p["other"], {**update, "content": update["content"] + " Add metrics."}
    )
    k.review(p["admin"], a["id"], "publish")
    with pytest.raises(KnowledgeError, match="版本已变化"):
        k.propose(p["writer"], update)
    with pytest.raises(KnowledgeError):
        k.propose(p["writer"], {**update, "base_version": None})
    with pytest.raises(KnowledgeError, match="已变更"):
        k.review(p["admin"], b["id"], "publish")
    restored = k.rollback(p["admin"], did, 1, 2)
    assert restored["version"] == 3 and svc.read(did)["content"] == payload()["content"]
    assert len(k.versions(did)) == 3
    with pytest.raises(KnowledgeError):
        k.rollback(p["admin"], did, 1, 2)
    assert k.propose(p["other"], payload())["status"] == "duplicate"


def test_categories_reject_cycles_and_pagination(env):
    c, p, client = env
    a = c.knowledge.save_category("A")["id"]
    b = c.knowledge.save_category("B", a)["id"]
    with pytest.raises(KnowledgeError):
        c.knowledge.save_category("A", b, a)
    assert (
        client("writer").post("/api/v1/categories", json={"name": "No"}).status_code
        == 403
    )
    c.repo.upsert(
        DocInput(
            "imported",
            "Imported reference",
            "A documented known behavior with enough reusable detail.",
            "yuque",
        )
    )
    assert c.repo.get("imported")["category_id"] == "seeyon-v8"
    assert len(c.knowledge.versions("imported")) == 1
    c.knowledge.bootstrap()
    c.knowledge.bootstrap()
    assert len(c.knowledge.versions("imported")) == 1
    c.repo.upsert(
        DocInput(
            "imported",
            "Imported reference",
            "A changed known behavior with enough reusable detail.",
            "yuque",
        )
    )
    assert c.repo.get("imported")["knowledge_version"] == 2
    assert len(c.knowledge.versions("imported")) == 2
    c.knowledge.delete_category(b)
    c.knowledge.delete_category(a)


def test_auto_publication_requires_admin_policy_quality_and_novelty(env):
    c, p, client = env
    prefix = p["writer"].key_prefix
    assert (
        client("writer")
        .put("/api/v1/admin/keys/" + prefix + "/policy", json={"auto_publish": True})
        .status_code
        == 403
    )
    assert (
        client("admin")
        .put("/api/v1/admin/keys/" + prefix + "/policy", json={"auto_publish": True})
        .status_code
        == 200
    )
    published = c.knowledge.propose(p["writer"], payload())
    assert published["status"] == "published"
    assert c.db.scalar("SELECT COUNT(*) FROM knowledge_audit") == 1
    manual = {
        **payload(),
        "source": "manual",
        "title": "Another novel manual topic",
        "content": "Manual content with enough details but no verification requirements.",
    }
    candidate = c.knowledge.propose(p["writer"], manual)
    assert candidate["status"] == "pending"
    with pytest.raises(KnowledgeError):
        c.knowledge.review(p["writer"], candidate["id"], "publish", trusted=True)
    assert (
        client("writer")
        .post("/api/v1/contributions", json={**payload(), "verified": False})
        .status_code
        == 422
    )
    result = client("writer").post(
        "/api/v1/knowledge", json={**manual, "source": "yuque"}
    )
    assert result.status_code == 422
    result = client("writer").post(
        "/api/v1/knowledge", json={**manual, "source": "agent"}
    )
    assert result.status_code == 200 and result.json()["status"] == "pending"
    secret = {
        **manual,
        "content": "secret wb_wr_" + "X" * 32 + " should not be uploaded",
    }
    assert (
        client("writer").post("/api/v1/contributions", json=secret).status_code == 400
    )


def test_standards_and_review_changes(env):
    c, p, client = env
    r = client("admin").post(
        "/api/v1/standards",
        json={
            "name": "Operations checks",
            "category_id": "operations",
            "checklist": ["Verify health", "Record rollback steps"],
        },
    )
    assert r.status_code == 200
    assert (
        len(
            client("reader")
            .get("/api/v1/standards?category_id=technology")
            .json()["standards"]
        )
        == 1
    )
    assert (
        client("writer").delete("/api/v1/standards/" + r.json()["id"]).status_code
        == 403
    )
    assert (
        client("admin").delete("/api/v1/standards/" + r.json()["id"]).status_code == 200
    )
    a = c.knowledge.propose(p["writer"], payload())
    c.knowledge.review(p["admin"], a["id"], "changes_requested", "Add context")
    a = c.knowledge.propose(p["writer"], payload(), True, a["id"])
    assert a["status"] == "pending"
    assert len(a["events"]) == 3


def test_queue_retry_blocking_and_project_opt_in(env, tmp_path, monkeypatch, capsys):
    import httpx

    from cli import knowledge as q
    from cli.wb import Client

    monkeypatch.setenv("TEAMKB_QUEUE_DIR", str(tmp_path / "queue"))
    c = Client("https://team.example", "secret-not-persisted")
    root = tmp_path / "project"
    root.mkdir()
    assert q.complete(c, root)["status"] == "disabled"
    q.write_json(root / ".teamkb" / "config.json", {"enabled": True})
    q.write_json(root / ".teamkb" / "candidate.json", payload())

    def down(*a):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(q, "send", down)
    result = q.complete(c, root)
    assert result["status"] == "queued"
    path = next((tmp_path / "queue").glob("*.json"))
    assert "secret-not-persisted" not in path.read_text()
    assert path.stat().st_mode & 0o777 == 0o600
    for i in range(4):
        entry = json.loads(path.read_text())
        entry["next_retry_at"] = 0
        q.write_json(path, entry)
        result = q.deliver(c, entry["payload"])
    assert result["status"] == "exhausted"
    entry = json.loads(path.read_text())
    entry.update(status="queued", attempts=0, next_retry_at=0)
    q.write_json(path, entry)
    monkeypatch.setattr(q, "send", lambda *a: httpx.Response(401))
    assert q.deliver(c, entry["payload"])["status"] == "blocked"
    q.write_json(
        root / ".teamkb" / "config.json",
        {"enabled": True, "candidate_file": "../escape.json"},
    )
    with pytest.raises(ValueError, match="项目内"):
        q.complete(c, root)
    entry.update(status="queued", attempts=0, next_retry_at=0)
    q.write_json(path, entry)
    monkeypatch.setattr(
        q,
        "send",
        lambda *a: httpx.Response(200, json={"status": "pending", "id": "test"}),
    )
    q.write_json(root / ".teamkb" / "config.json", {"enabled": True})
    assert q.complete(c, root)["status"] == "pending"
    assert q.complete(c, root)["status"] == "unchanged"
    assert not list((tmp_path / "queue").glob("*.json"))


def test_library_sort_is_applied_before_pagination(env):
    c, _, client = env
    for did, title in [("sort-b", "Beta"), ("sort-a", "Alpha"), ("sort-c", "Charlie")]:
        c.repo.upsert(
            DocInput(
                did,
                title,
                "A reusable reference for collection ordering and pagination.",
                "manual",
                tags=["sort-test"],
            )
        )
    first = (
        client("reader")
        .get("/api/v1/library?sort=title&page_size=1&tag=sort-test")
        .json()
    )
    second = (
        client("reader")
        .get("/api/v1/library?sort=title&page_size=1&page=2&tag=sort-test")
        .json()
    )
    assert (
        first["documents"][0]["title"] == "Alpha"
        and second["documents"][0]["title"] == "Beta"
    )
    assert first["total"] == 3
    oldest = (
        client("reader")
        .get("/api/v1/library?sort=oldest&page_size=1&tag=sort-test")
        .json()
    )
    assert oldest["documents"][0]["title"] == "Beta"
    assert client("reader").get("/api/v1/library?sort=invalid").status_code == 422
