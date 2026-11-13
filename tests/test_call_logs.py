"""Personal request/result history, authorization boundaries and capture fidelity."""

import json
import time
from pathlib import Path
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.api import http_app, accounts as account_routes
from server.config import Settings
from server.core.container import Container
from server.core.call_logs import (
    CallLogService,
    REQUEST_LIMIT,
    RESPONSE_LIMIT,
    snapshot,
)
from server.core.docs import DocInput


@pytest.fixture
def env(tmp_path, monkeypatch):
    c = Container(
        Settings(data_dir=tmp_path, require_auth=True, bootstrap_admin_key="")
    )
    monkeypatch.setattr(http_app, "get_container", lambda: c)
    monkeypatch.setattr(account_routes, "get_container", lambda: c)
    admin, _ = c.auth.create_key("old admin", "admin")
    actor = c.auth.authenticate(admin)
    users = []
    sessions = []
    keys = []
    for name in ["alice", "bob"]:
        u = c.accounts.register(name, name.title(), "password-12345!")
        c.accounts.review(u["id"], "approved", "writer", "", actor)
        token, _ = c.accounts.login(name, "password-12345!")
        client = TestClient(
            http_app.app,
            base_url="https://testserver",
            headers={"X-Requested-With": "V8Workbench"},
        )
        client.cookies.set("v8wb_session", token)
        users.append(u)
        sessions.append(client)
        raw, _ = c.auth.create_key(name + " agent", "writer", owner_user_id=u["id"])
        keys.append(raw)
    c.repo.upsert(
        DocInput(
            id="test-doc",
            title="组织同步开发指南",
            body="组织同步开发指南的实际正文，包含平台扩展与开发规范内容。",
            source="manual",
        )
    )
    c.rebuild_index()

    def key_client(raw, **kwargs):
        return TestClient(
            http_app.app,
            base_url="https://testserver",
            headers={"Authorization": "Bearer " + raw, "X-V8WB-Client": "cli"},
            **kwargs,
        )

    return c, users, sessions, keys, key_client, admin


def test_session_and_key_history_aggregate_without_cross_user_leak(env):
    c, users, sessions, keys, key_client, _ = env
    assert (
        sessions[0].post("/api/v1/search", json={"query": "组织同步"}).status_code
        == 200
    )
    a = key_client(keys[0])
    b = key_client(keys[1])
    assert a.post("/api/v1/read", json={"id": "test-doc"}).status_code == 200
    assert b.post("/api/v1/rules", json={"task": "spi"}).status_code == 200
    logs = sessions[0].get("/api/v1/account/calls").json()
    assert logs["total"] == 2 and logs["scope"] == "account"
    assert {log["client"] for log in logs["logs"]} == {"web", "cli"}
    assert logs["summary"]["success"] == 2
    assert "response" not in logs["logs"][0]
    detail = (
        sessions[0].get("/api/v1/account/calls/" + str(logs["logs"][0]["id"])).json()
    )
    assert detail["response"]["title"] == "组织同步开发指南"
    assert detail["request"] == {"id": "test-doc"}
    assert detail["user_id"] == users[0]["id"] and detail["duration_ms"] >= 0
    assert (
        sessions[1].get("/api/v1/account/calls/" + str(detail["id"])).status_code == 404
    )
    assert b.get("/api/v1/account/calls/" + str(detail["id"])).status_code == 404
    assert (
        sessions[1]
        .get("/api/v1/account/calls?user_id=" + users[0]["id"])
        .json()["total"]
        == 1
    )
    assert c.db.scalar("SELECT COUNT(*) FROM call_logs") == 3


def test_key_scope_is_limited_to_that_key_and_revoked_history_remains(env):
    c, users, sessions, keys, key_client, _ = env
    other, _ = c.auth.create_key("second key", owner_user_id=users[0]["id"])
    a = key_client(keys[0])
    second = key_client(other)
    a.get("/api/v1/stats")
    second.get("/api/v1/domains")
    sessions[0].get("/api/v1/recent")
    assert a.get("/api/v1/account/calls").json()["total"] == 1
    second_id = second.get("/api/v1/account/calls").json()["logs"][0]["id"]
    assert a.get("/api/v1/account/calls/" + str(second_id)).status_code == 404
    assert sessions[0].get("/api/v1/account/calls").json()["total"] == 3
    c.auth.revoke(c.auth.authenticate(other).key_prefix)
    history = sessions[0].get("/api/v1/account/calls").json()
    assert history["total"] == 3
    assert history["logs"][1]["key_prefix"] in history["keys"]
    assert second.get("/api/v1/account/calls").status_code == 401


def test_handled_failures_validation_and_quota_are_logged_correctly(env):
    c, _, _, keys, key_client, _ = env
    a = key_client(keys[0])
    assert a.post("/api/v1/read", json={"id": "missing"}).status_code == 400
    assert a.post("/api/v1/search", json={"query": "x", "limit": 0}).status_code == 422
    assert a.delete("/api/v1/knowledge/test-doc").status_code == 403
    with c.db.write() as db:
        db.execute(
            "UPDATE api_keys SET daily_limit=1 WHERE key_hash=?",
            (__import__("hashlib").sha256(keys[0].encode()).hexdigest(),),
        )
    assert a.get("/api/v1/stats").status_code == 429
    history = a.get("/api/v1/account/calls").json()
    assert history["summary"]["failed"] == 4 and history["total"] == 4
    assert {log["status_code"] for log in history["logs"]} == {400, 422, 403, 429}
    # Merely reading history or a history detail never adds entries or burns quota.
    a.get("/api/v1/account/calls/" + str(history["logs"][0]["id"]))
    assert c.db.scalar("SELECT COUNT(*) FROM usage_log") == 4
    assert c.db.scalar("SELECT COUNT(*) FROM call_logs") == 4


def test_successful_invocation_is_counted_exactly_once(env):
    c, _, _, keys, key_client, _ = env
    a = key_client(keys[0])
    a.post("/api/v1/read", json={"id": "test-doc"})
    assert c.db.scalar("SELECT COUNT(*) FROM usage_log") == 1
    assert c.db.scalar("SELECT COUNT(*) FROM call_logs") == 1
    assert (
        c.auth.list_keys(owner_user_id=c.auth.authenticate(keys[0]).user_id)[0][
            "used_today"
        ]
        == 1
    )


def test_partial_batch_result_is_preserved_and_marked_partial(env):
    _, _, _, keys, key_client, _ = env
    a = key_client(keys[0])
    result = a.post(
        "/api/v1/knowledge/batch",
        json=[
            {
                "title": "Good",
                "content": "a valid knowledge item with enough reusable details for testing.",
            },
            {"title": "Empty", "content": ""},
        ],
    )
    assert result.status_code == 200 and result.json()["failed"]
    history = a.get("/api/v1/account/calls").json()
    assert history["summary"]["partial"] == 1
    detail = a.get("/api/v1/account/calls/" + str(history["logs"][0]["id"])).json()
    assert detail["outcome"] == "partial" and detail["response"] == result.json()


def test_sensitive_fields_headers_tokens_and_query_secrets_are_not_persisted(env):
    c, _, _, keys, key_client, _ = env
    a = key_client(keys[0])
    a.headers["X-V8WB-Client"] = "mcp"
    result = a.post(
        "/api/v1/search?api_key=query-secret",
        json={
            "query": "组织同步 " + keys[0],
            "password": "plain-password",
            "nested": {"apiKey": "another-secret", "token": "private-token"},
        },
    )
    assert result.status_code == 200
    row = c.db.one("SELECT * FROM call_logs")
    saved = str(dict(row))
    for secret in [
        keys[0],
        "plain-password",
        "another-secret",
        "private-token",
        "query-secret",
        "v8wb_session",
    ]:
        assert secret not in saved
    assert row["client"] == "mcp" and "[已隐藏]" in saved
    assert row["user_id"] == c.auth.authenticate(keys[0]).user_id
    from server.core.call_logs import clean_text

    assert keys[0] not in clean_text("中文紧接" + keys[0] + "后缀")
    assert result.json()["query"].endswith(keys[0])  # Client result is unchanged.


def test_truncation_is_bounded_without_changing_business_response(env):
    c, _, _, keys, key_client, _ = env
    body = "组织同步内容。" * 10000
    c.repo.upsert(DocInput(id="long", title="超长组织文档", body=body, source="manual"))
    c.rebuild_index()
    a = key_client(keys[0])
    result = a.post("/api/v1/read", json={"id": "long", "max_chars": 60000})
    assert len(result.json()["content"]) == 60000
    log = a.get("/api/v1/account/calls").json()["logs"][0]
    assert log["response_truncated"]
    detail = a.get("/api/v1/account/calls/" + str(log["id"])).json()
    assert detail["response_truncated"] and detail["outcome"] == "success"
    assert (
        len(json.dumps(detail["response"], ensure_ascii=False).encode())
        < RESPONSE_LIMIT + 2048
    )
    raw = json.dumps({"query": "x" * (REQUEST_LIMIT * 2)}).encode()
    value, truncated = snapshot(raw[:REQUEST_LIMIT], len(raw), REQUEST_LIMIT)
    assert truncated and value


def test_legacy_key_logs_are_private_to_the_current_legacy_key(env):
    _, _, _, keys, key_client, admin = env
    root = key_client(admin)
    root.get("/api/v1/stats")
    own = root.get("/api/v1/account/calls").json()
    assert own["scope"] == "key" and own["total"] == 1
    a = key_client(keys[0])
    a.get("/api/v1/stats")
    assert (
        root.get("/api/v1/account/calls").json()["total"] == 1
    )  # Admin has no global log bypass.
    assert (
        root.get(
            "/api/v1/account/calls/"
            + str(a.get("/api/v1/account/calls").json()["logs"][0]["id"])
        ).status_code
        == 404
    )


def test_filters_pagination_and_parameter_bounds(env):
    _, _, _, keys, key_client, _ = env
    a = key_client(keys[0])
    for query in ["组织同步", "SPI", "UDC"]:
        a.post("/api/v1/search", json={"query": query})
    a.post("/api/v1/read", json={"id": "missing"})
    selected = a.get(
        "/api/v1/account/calls?operation=search&client=cli&outcome=success&page_size=1&page=2"
    ).json()
    assert selected["total"] == 3 and len(selected["logs"]) == 1
    assert selected["logs"][0]["request_summary"] == "SPI"
    assert a.get("/api/v1/account/calls?query=组织同步").json()["total"] == 1
    assert a.get("/api/v1/account/calls?query=%25").json()["total"] == 0
    assert (
        a.get("/api/v1/account/calls?since=" + str(int(time.time() + 30))).json()[
            "total"
        ]
        == 0
    )
    assert a.get("/api/v1/account/calls?page_size=1000").status_code == 422
    assert a.get("/api/v1/account/calls?outcome=unknown").status_code == 422
    assert a.get("/api/v1/account/calls?since=30&until=20").status_code == 400


def test_retention_and_capacity_do_not_reset_daily_quota(env):
    c, _, _, keys, _, _ = env
    service = CallLogService(c.db, retention_days=1, max_entries=2)
    p = c.auth.authenticate(keys[0])

    def record(ts):
        service.record(
            p,
            operation="stats",
            method="GET",
            path="/api/v1/stats",
            client="api",
            status=200,
            duration_ms=2,
            request_data=None,
            response_data={"documents": 1},
            ts=ts,
        )

    record(time.time() - 2 * 86400)
    for i in range(3):
        record(time.time() + i * 0.01)
        c.auth.log_usage(p, "stats", True)
    assert service.list(p)["total"] == 2
    assert c.db.scalar("SELECT COUNT(*) FROM call_logs") == 2
    assert c.db.scalar("SELECT COUNT(*) FROM usage_log") == 3


def test_unhandled_failure_is_logged_without_exception_payload(env, monkeypatch):
    c, _, _, keys, key_client, _ = env

    class Broken:
        def stats(self):
            raise RuntimeError("do not leak internal secret")

    monkeypatch.setattr(http_app, "_svc", lambda: Broken())
    a = key_client(keys[0], raise_server_exceptions=False)
    assert a.get("/api/v1/stats").status_code == 500
    log = c.db.one("SELECT * FROM call_logs")
    assert log["status_code"] == 500 and log["outcome"] == "failed"
    assert "do not leak" not in log["response_json"]


def test_logging_failure_does_not_break_successful_response(env, monkeypatch):
    c, _, _, keys, key_client, _ = env

    def broken(*args, **kwargs):
        raise OSError("storage failed")

    monkeypatch.setattr(c.calls, "record", broken)
    result = key_client(keys[0]).get("/api/v1/stats")
    assert result.status_code == 200 and "documents" in result.json()
    assert c.db.scalar("SELECT COUNT(*) FROM usage_log") == 1


def test_oversized_snapshot_redacts_before_truncating_and_discards_unparseable_body():
    secret = "plain-credential-value"
    raw = json.dumps(
        {"password": secret, "content": "x" * (RESPONSE_LIMIT * 2)}
    ).encode()
    saved, truncated = snapshot(raw, len(raw), RESPONSE_LIMIT)
    assert truncated and secret not in json.dumps(saved)
    assert len(json.dumps(saved, ensure_ascii=False).encode()) <= RESPONSE_LIMIT
    partial, truncated = snapshot(
        b'{"password":"plain-credential', 100000, REQUEST_LIMIT
    )
    assert truncated and "plain-credential" not in json.dumps(partial)


def test_interrupted_response_keeps_sent_http_status_and_marks_failure(env):
    import asyncio
    from server.api.call_logging import CallLoggingMiddleware

    c, _, _, keys, _, _ = env
    p = c.auth.authenticate(keys[0])

    async def interrupted(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send(
            {
                "type": "http.response.body",
                "body": b'{"documents":1}',
                "more_body": True,
            }
        )
        raise RuntimeError("stream interrupted")

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        pass

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/stats",
        "state": {"call_principal": p},
        "headers": [],
        "query_string": b"",
    }
    with pytest.raises(RuntimeError):
        asyncio.run(CallLoggingMiddleware(interrupted, lambda: c)(scope, receive, send))
    record = c.db.one("SELECT * FROM call_logs")
    assert record["status_code"] == 200 and record["outcome"] == "failed"
