"""Account lifecycle and HTTP authorization integration tests, isolated from live data."""

import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.api import accounts as routes
from server.api import http_app
from server.config import Settings
from server.core.accounts import AccountError
from server.core.auth import AuthError, hash_key
from server.core.container import Container
from server.core.db import Database

PASSWORD = "test-password-123!"


@pytest.fixture
def env(tmp_path, monkeypatch):
    c = Container(
        Settings(data_dir=tmp_path, require_auth=True, bootstrap_admin_key="")
    )
    monkeypatch.setattr(http_app, "get_container", lambda: c)
    monkeypatch.setattr(routes, "get_container", lambda: c)
    admin_key, _ = c.auth.create_key("legacy admin", "admin")

    def client():
        return TestClient(
            http_app.app,
            base_url="https://testserver",
            headers={"X-Requested-With": "V8Workbench"},
        )

    admin = client()
    admin.headers["Authorization"] = "Bearer " + admin_key
    return c, client, admin, admin_key


def register(client, name="alice"):
    response = client.post(
        "/api/v1/auth/register",
        json={"username": name, "display_name": name.title(), "password": PASSWORD},
    )
    assert response.status_code == 201, response.text
    user = response.json()["user"]
    assert "password_hash" not in user
    return user


def login(client, name="alice", password=PASSWORD):
    r = client.post("/api/v1/auth/login", json={"username": name, "password": password})
    assert r.status_code == 200, r.text
    return r


def approve(admin, user, role="writer", status="approved"):
    r = admin.patch(
        "/api/v1/admin/users/" + user["id"],
        json={"status": status, "role": role, "note": "身份已核实"},
    )
    assert r.status_code == 200, r.text
    return r


def create_key(client, role="reader"):
    r = client.post("/api/v1/account/keys", json={"name": "my agent", "role": role})
    assert r.status_code == 201, r.text
    return r.json()


def test_pending_rejected_and_disabled_cannot_use_workbench(env):
    _, client, admin, _ = env
    member = client()
    user = register(member)
    login(member)
    assert member.get("/api/v1/auth/me").json()["user"]["status"] == "pending"
    for path in ["/api/v1/stats", "/api/v1/account/keys", "/api/v1/admin/users"]:
        assert member.get(path).status_code == 403
    assert member.post("/api/v1/search", json={"query": "SPI"}).status_code == 403
    assert member.post("/api/v1/account/keys", json={"name": "test"}).status_code == 403
    approve(admin, user, status="rejected")
    assert member.get("/api/v1/auth/me").json()["user"]["status"] == "rejected"
    assert member.get("/api/v1/stats").status_code == 403
    approve(admin, user)
    assert member.get("/api/v1/stats").status_code == 200
    approve(admin, user, status="disabled")
    assert member.get("/api/v1/stats").status_code == 403


def test_key_ownership_scope_and_role_caps(env):
    c, client, admin, _ = env
    alice, bob = client(), client()
    a, b = register(alice), register(bob, "bob")
    approve(admin, a)
    approve(admin, b)
    login(alice)
    login(bob, "bob")
    key = create_key(alice, "writer")
    assert (
        alice.post(
            "/api/v1/account/keys", json={"name": "admin attempt", "role": "admin"}
        ).status_code
        == 403
    )
    assert bob.get("/api/v1/account/keys").json()["keys"] == []
    assert bob.delete("/api/v1/account/keys/" + key["prefix"]).status_code == 404
    owned = alice.get("/api/v1/account/keys").json()["keys"]
    assert owned[0]["owner_user_id"] == a["id"]
    assert key["key"] not in str(owned)
    assert alice.get("/api/v1/admin/users").status_code == 403
    assert alice.get("/api/v1/admin/keys").status_code == 403
    api_client = client()
    api_client.headers["Authorization"] = "Bearer " + key["key"]
    assert api_client.get("/api/v1/stats").status_code == 200
    # Key ownership alone does not create a browser login session.
    assert api_client.get("/api/v1/account/keys").status_code == 401
    assert c.auth.authenticate(key["key"]).user_id == a["id"]
    approve(admin, a, role="reader")
    assert c.auth.authenticate(key["key"]).role == "reader"
    assert (
        api_client.post(
            "/api/v1/knowledge", json={"title": "test", "content": "a" * 30}
        ).status_code
        == 403
    )
    assert alice.delete("/api/v1/account/keys/" + key["prefix"]).status_code == 200
    assert api_client.get("/api/v1/stats").status_code == 401


def test_disabling_revokes_keys_and_approval_does_not_revive_them(env):
    c, client, admin, _ = env
    user_client = client()
    user = register(user_client)
    approve(admin, user)
    login(user_client)
    key = create_key(user_client)
    approve(admin, user, status="disabled")
    with pytest.raises(AuthError):
        c.auth.authenticate(key["key"])
    approve(admin, user)
    with pytest.raises(AuthError):
        c.auth.authenticate(key["key"])
    assert create_key(user_client)["key"] != key["key"]
    assert (
        len(
            c.db.query(
                "SELECT * FROM account_audit WHERE target_user_id=?", (user["id"],)
            )
        )
        == 3
    )


def test_password_hash_session_cookie_logout_and_password_change(env):
    c, client, _, _ = env
    first, second = client(), client()
    user = register(first)
    response = login(first)
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "secure" in cookie and "samesite=lax" in cookie
    session = first.cookies.get("v8wb_session")
    assert c.db.one("SELECT token_hash FROM user_sessions")[0] != session
    stored = c.db.one("SELECT password_hash FROM users WHERE id=?", (user["id"],))[0]
    assert PASSWORD not in stored and stored.startswith("pbkdf2_sha256$")
    login(second)
    assert (
        first.post(
            "/api/v1/auth/password",
            json={"current_password": "wrong", "new_password": "new-password-123!"},
        ).status_code
        == 400
    )
    assert (
        first.post(
            "/api/v1/auth/password",
            json={"current_password": PASSWORD, "new_password": "new-password-123!"},
        ).status_code
        == 200
    )
    assert second.get("/api/v1/auth/me").status_code == 401
    assert c.db.scalar("SELECT COUNT(*) FROM user_sessions") == 0
    assert (
        first.post(
            "/api/v1/auth/login", json={"username": "alice", "password": PASSWORD}
        ).status_code
        == 401
    )
    login(first, password="new-password-123!")
    assert first.post("/api/v1/auth/logout").status_code == 200
    assert first.get("/api/v1/auth/me").status_code == 401


def test_cookie_mutations_reject_cross_origin_requests(env):
    _, client, admin, _ = env
    member = client()
    user = register(member)
    approve(admin, user)
    login(member)
    assert (
        member.post(
            "/api/v1/account/keys",
            json={"name": "bad"},
            headers={"Origin": "https://evil.example"},
        ).status_code
        == 403
    )
    assert (
        member.post(
            "/api/v1/auth/logout", headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert (
        member.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": PASSWORD},
            headers={"Origin": "https://evil.example"},
        ).status_code
        == 403
    )
    member.headers.pop("X-Requested-With")
    assert member.post("/api/v1/account/keys", json={"name": "bad"}).status_code == 403
    good = member.post(
        "/api/v1/account/keys",
        json={"name": "good"},
        headers={"Origin": "https://testserver"},
    )
    assert good.status_code == 201
    assert good.headers["cache-control"] == "no-store"
    assert "Cookie" in good.headers["vary"]


def test_registration_validation_case_and_persistent_throttle(env):
    c, client, _, _ = env
    member = client()
    register(member, "ALICE")
    assert (
        member.post(
            "/api/v1/auth/register",
            json={"username": "alice", "display_name": "other", "password": PASSWORD},
        ).status_code
        == 409
    )
    assert (
        member.post(
            "/api/v1/auth/register",
            json={
                "username": "a bad name",
                "display_name": "other",
                "password": PASSWORD,
            },
        ).status_code
        == 400
    )
    assert (
        member.post(
            "/api/v1/auth/register",
            json={"username": "other", "display_name": "other", "password": "123"},
        ).status_code
        == 422
    )
    c.accounts.throttle("test", "ip", 1)
    with pytest.raises(AccountError) as error:
        c.accounts.throttle("test", "ip", 1)
    assert error.value.status == 429
    assert (
        member.post(
            "/api/v1/auth/login", json={"username": "missing", "password": PASSWORD}
        ).json()["message"]
        == "用户名或密码不正确"
    )


def test_legacy_admin_can_bootstrap_account_admin_and_last_admin_is_protected(env):
    c, client, admin, raw = env
    member = client()
    user = register(member)
    assert admin.get("/api/v1/admin/users").status_code == 200
    approve(admin, user, role="admin")
    login(member)
    assert member.get("/api/v1/admin/users").status_code == 200
    self_disable = member.patch(
        "/api/v1/admin/users/" + user["id"],
        json={"status": "disabled", "role": "admin"},
    )
    assert self_disable.status_code == 400
    assert (
        admin.patch(
            "/api/v1/admin/users/" + user["id"],
            json={"status": "approved", "role": "reader"},
        ).status_code
        == 400
    )
    key = member.post(
        "/api/v1/admin/keys", json={"name": "owned admin", "role": "admin"}
    )
    assert key.status_code == 200
    assert c.auth.authenticate(key.json()["key"]).user_id == user["id"]
    assert c.auth.authenticate(raw).role == "admin"
    assert c.auth.authenticate(raw).user_id is None


def test_personal_key_limit_and_no_cross_account_role_escalation(env):
    c, client, admin, _ = env
    member = client()
    user = register(member)
    approve(admin, user, role="reader")
    login(member)
    assert (
        member.post(
            "/api/v1/account/keys", json={"name": "bad", "role": "writer"}
        ).status_code
        == 403
    )
    for i in range(20):
        c.auth.create_key(f"key-{i}", owner_user_id=user["id"])
    assert (
        member.post("/api/v1/account/keys", json={"name": "too many"}).status_code
        == 400
    )
    assert member.get("/api/v1/stats").status_code == 200


def test_existing_database_migrates_without_losing_legacy_keys(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE api_keys(key_hash TEXT PRIMARY KEY, key_prefix TEXT NOT NULL,name TEXT NOT NULL, role TEXT NOT NULL,rpm_limit INTEGER DEFAULT 120,daily_limit INTEGER DEFAULT 20000,enabled INTEGER DEFAULT 1,created_at REAL NOT NULL,last_used_at REAL DEFAULT 0,revoked_at REAL DEFAULT 0)"
        )
        conn.execute(
            "INSERT INTO api_keys(key_hash,key_prefix,name,role,created_at) VALUES (?,?,?,?,?)",
            (hash_key("legacy-secret"), "legacy", "old admin", "admin", 0),
        )
    db = Database(path)
    assert db.one("SELECT * FROM api_keys")["owner_user_id"] is None
    assert db.scalar("SELECT COUNT(*) FROM api_keys") == 1
    assert db.one("SELECT * FROM api_keys")["key_hash"] == hash_key("legacy-secret")
    Database(path)
    assert db.scalar("SELECT COUNT(*) FROM api_keys") == 1
