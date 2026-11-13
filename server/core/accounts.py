"""Registration review, password authentication and revocable browser sessions."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import sqlite3
import time

from .auth import ROLE_RANK, Principal, hash_key
from .db import Database

SESSION_TTL = 7 * 24 * 3600
PASSWORD_ITERATIONS = 600_000
# Equal-cost verification for unknown usernames.
_DUMMY_HASH = f"pbkdf2_sha256${PASSWORD_ITERATIONS}$dummy${hashlib.pbkdf2_hmac('sha256', b'not-a-user-password', b'dummy', PASSWORD_ITERATIONS).hex()}"


class AccountError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def password_hash(password: str) -> str:
    if not 10 <= len(password) <= 128:
        raise AccountError("密码长度需要在 10 到 128 个字符之间")
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), PASSWORD_ITERATIONS
    )
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, digest = encoded.split("$")
        if algorithm != "pbkdf2_sha256" or len(password) > 128:
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), int(iterations)
        ).hex()
        return hmac.compare_digest(actual, digest)
    except (ValueError, TypeError):
        return False


def public_user(row) -> dict:
    return {
        k: row[k]
        for k in (
            "id",
            "username",
            "display_name",
            "role",
            "status",
            "review_note",
            "created_at",
            "reviewed_at",
        )
    }


class AccountService:
    def __init__(self, db: Database, default_rpm: int, default_daily: int):
        self.db, self.default_rpm, self.default_daily = db, default_rpm, default_daily

    def throttle(self, action: str, identity: str, limit: int, window: int = 900):
        now = time.time()
        bucket = hash_key(action + ":" + identity)
        with self.db.write() as conn:
            conn.execute("DELETE FROM auth_attempts WHERE at < ?", (now - window,))
            count = conn.execute(
                "SELECT COUNT(*) FROM auth_attempts WHERE bucket=?", (bucket,)
            ).fetchone()[0]
            if count >= limit:
                raise AccountError("尝试次数过多，请在 15 分钟后重试", 429)
            conn.execute(
                "INSERT INTO auth_attempts(bucket, at) VALUES (?,?)", (bucket, now)
            )

    def register(self, username: str, display_name: str, password: str) -> dict:
        username = username.strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{2,31}", username):
            raise AccountError(
                "用户名需为 3–32 位英文字母、数字、点、下划线或短横线，并以字母或数字开头"
            )
        display_name = display_name.strip()
        if not 1 <= len(display_name) <= 60:
            raise AccountError("姓名需要在 1 到 60 个字符之间")
        encoded = password_hash(password)
        user_id = secrets.token_hex(16)
        try:
            with self.db.write() as conn:
                conn.execute(
                    "INSERT INTO users(id, username, display_name, password_hash, role, status, created_at) VALUES (?,?,?,?,?,'pending',?)",
                    (user_id, username, display_name, encoded, "reader", time.time()),
                )
        except sqlite3.IntegrityError as e:
            raise AccountError("该用户名已被注册", 409) from e
        return self.get_user(user_id)

    def get_user(self, user_id: str) -> dict:
        row = self.db.one("SELECT * FROM users WHERE id=?", (user_id,))
        if not row:
            raise AccountError("账号不存在", 404)
        return public_user(row)

    def login(self, username: str, password: str) -> tuple[str, dict]:
        row = self.db.one(
            "SELECT * FROM users WHERE username=?", (username.strip().lower(),)
        )
        valid = verify_password(password, row["password_hash"] if row else _DUMMY_HASH)
        if not row or not valid:
            raise AccountError("用户名或密码不正确", 401)
        raw = secrets.token_urlsafe(32)
        now = time.time()
        with self.db.write() as conn:
            conn.execute("DELETE FROM user_sessions WHERE expires_at < ?", (now,))
            conn.execute(
                "INSERT INTO user_sessions(token_hash,user_id,created_at,expires_at) VALUES (?,?,?,?)",
                (hash_key(raw), row["id"], now, now + SESSION_TTL),
            )
            # Bound the number of concurrent sessions per account.
            conn.execute(
                "DELETE FROM user_sessions WHERE user_id=? AND token_hash NOT IN (SELECT token_hash FROM user_sessions WHERE user_id=? ORDER BY created_at DESC LIMIT 10)",
                (row["id"], row["id"]),
            )
        return raw, public_user(row)

    def session_user(self, raw: str) -> dict:
        row = self.db.one(
            "SELECT u.* FROM user_sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>?",
            (hash_key(raw), time.time()),
        )
        if not row:
            raise AccountError("登录已失效，请重新登录", 401)
        return public_user(row)

    def require_approved(self, user: dict):
        if user["status"] != "approved":
            messages = {
                "pending": "账号正在等待管理员审批",
                "rejected": "入网申请未通过，请联系管理员",
                "disabled": "账号已停用，请联系管理员",
            }
            raise AccountError(messages.get(user["status"], "账号不可用"), 403)

    def principal(self, raw: str) -> Principal:
        user = self.session_user(raw)
        self.require_approved(user)
        return Principal(
            "user:" + user["id"],
            user["display_name"],
            user["role"],
            self.default_rpm,
            self.default_daily,
            user_id=user["id"],
            kind="session",
        )

    def logout(self, raw: str):
        with self.db.write() as conn:
            conn.execute(
                "DELETE FROM user_sessions WHERE token_hash=?", (hash_key(raw),)
            )

    def change_password(self, user_id: str, current: str, new: str):
        encoded = password_hash(new)
        with self.db.write() as conn:
            row = conn.execute(
                "SELECT password_hash FROM users WHERE id=?", (user_id,)
            ).fetchone()
            if not row or not verify_password(current, row["password_hash"]):
                raise AccountError("当前密码不正确", 400)
            conn.execute(
                "UPDATE users SET password_hash=? WHERE id=?", (encoded, user_id)
            )
            conn.execute("DELETE FROM user_sessions WHERE user_id=?", (user_id,))

    def list_users(self) -> list[dict]:
        return [
            public_user(row)
            for row in self.db.query(
                "SELECT * FROM users ORDER BY CASE WHEN status='pending' THEN 0 ELSE 1 END, created_at DESC"
            )
        ]

    def review(
        self, user_id: str, status: str, role: str, note: str, actor: Principal
    ) -> dict:
        if status not in {"approved", "rejected", "disabled"} or role not in ROLE_RANK:
            raise AccountError("无效的审批状态或角色")
        now = time.time()
        with self.db.write() as conn:
            target = conn.execute(
                "SELECT * FROM users WHERE id=?", (user_id,)
            ).fetchone()
            if not target:
                raise AccountError("账号不存在", 404)
            if actor.user_id == user_id and (status != "approved" or role != "admin"):
                raise AccountError("不能停用或降级当前管理员账号")
            if (
                target["role"] == "admin"
                and target["status"] == "approved"
                and (status != "approved" or role != "admin")
            ):
                remaining = conn.execute(
                    "SELECT COUNT(*) FROM users WHERE role='admin' AND status='approved' AND id!=?",
                    (user_id,),
                ).fetchone()[0]
                if not remaining:
                    raise AccountError("至少保留一个已批准的管理员账号")
            conn.execute(
                "UPDATE users SET status=?, role=?, review_note=?, reviewed_at=?, reviewed_by=? WHERE id=?",
                (
                    status,
                    role,
                    note.strip()[:500],
                    now,
                    actor.user_id or actor.key_prefix,
                    user_id,
                ),
            )
            conn.execute(
                "INSERT INTO account_audit(actor,target_user_id,status,role,note,at) VALUES (?,?,?,?,?,?)",
                (
                    actor.user_id or actor.key_prefix,
                    user_id,
                    status,
                    role,
                    note.strip()[:500],
                    now,
                ),
            )
            if status != "approved":
                conn.execute(
                    "UPDATE api_keys SET enabled=0,revoked_at=? WHERE owner_user_id=? AND enabled=1",
                    (now, user_id),
                )
                # Existing sessions can still display account status, but all work APIs reject them.
        return self.get_user(user_id)
