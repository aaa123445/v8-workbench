"""API Key 鉴权 + 配额。

Key 格式：wb_<role-short>_<32位随机>  —— 前缀明文存库便于管理员识别，本体只存哈希。
角色：
  admin  读写一切、管 key、触发同步
  writer 可提交/上传知识（本地 agent 自动推送用这个）
  reader 只读检索
"""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass
from datetime import date

from .db import Database

ROLE_RANK = {"reader": 1, "writer": 2, "admin": 3}
_ROLE_TAG = {"reader": "rd", "writer": "wr", "admin": "ad"}


@dataclass
class Principal:
    key_prefix: str
    name: str
    role: str
    rpm_limit: int
    daily_limit: int
    user_id: str | None = None
    kind: str = "key"

    def can(self, need: str) -> bool:
        return ROLE_RANK.get(self.role, 0) >= ROLE_RANK.get(need, 99)


class QuotaExceeded(Exception):
    def __init__(self, message: str, retry_after: int = 60) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class AuthError(Exception):
    pass


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _prefix_of(raw: str) -> str:
    # wb_wr_abcdefgh... -> 取到第二段 + 前 6 位，便于识别又不泄露
    parts = raw.split("_")
    if len(parts) >= 3:
        return f"{parts[1]}_{parts[2][:6]}"
    return raw[:10]


class AuthService:
    def __init__(
        self, db: Database, *, require_auth: bool, default_rpm: int, default_daily: int
    ) -> None:
        self.db = db
        self.require_auth = require_auth
        self.default_rpm = default_rpm
        self.default_daily = default_daily
        self._rpm_bucket: dict[str, list[float]] = {}

    # ---------- key 管理 ----------

    def create_key(
        self,
        name: str,
        role: str = "reader",
        *,
        rpm: int | None = None,
        daily: int | None = None,
        owner_user_id: str | None = None,
    ) -> tuple[str, dict]:
        if role not in ROLE_RANK:
            raise AuthError(f"未知角色：{role}")
        tag = _ROLE_TAG[role]
        raw = f"wb_{tag}_{secrets.token_urlsafe(24)}"
        prefix = _prefix_of(raw)
        now = time.time()
        with self.db.write() as conn:
            if owner_user_id:
                owner = conn.execute(
                    "SELECT role,status FROM users WHERE id=?", (owner_user_id,)
                ).fetchone()
                if (
                    not owner
                    or owner["status"] != "approved"
                    or ROLE_RANK[role] > ROLE_RANK.get(owner["role"], 0)
                ):
                    raise AuthError("账号未获批准，或 Key 角色超过账号权限")
                count = conn.execute(
                    "SELECT COUNT(*) FROM api_keys WHERE owner_user_id=? AND enabled=1",
                    (owner_user_id,),
                ).fetchone()[0]
                if count >= 20:
                    raise AuthError(
                        "每个账号最多启用 20 个 Key，请先吊销不再使用的 Key"
                    )
            while conn.execute(
                "SELECT 1 FROM api_keys WHERE key_prefix=?", (prefix,)
            ).fetchone():
                raw = f"wb_{tag}_{secrets.token_urlsafe(24)}"
                prefix = _prefix_of(raw)
            conn.execute(
                """INSERT INTO api_keys (key_hash, key_prefix, name, role, rpm_limit, daily_limit,
                                         enabled, created_at, owner_user_id)
                   VALUES (?,?,?,?,?,?,1,?,?)""",
                (
                    hash_key(raw),
                    prefix,
                    name,
                    role,
                    rpm or self.default_rpm,
                    daily or self.default_daily,
                    now,
                    owner_user_id,
                ),
            )
        return raw, {"prefix": prefix, "name": name, "role": role}

    def revoke(self, prefix: str, *, owner_user_id: str | None = None) -> bool:
        with self.db.write() as conn:
            cur = conn.execute(
                "UPDATE api_keys SET enabled = 0, revoked_at = ? WHERE key_prefix = ? AND enabled = 1"
                + (" AND owner_user_id=?" if owner_user_id is not None else ""),
                (time.time(), prefix, owner_user_id)
                if owner_user_id is not None
                else (time.time(), prefix),
            )
            return cur.rowcount > 0

    def list_keys(self, *, owner_user_id: str | None = None) -> list[dict]:
        rows = self.db.query(
            """SELECT k.key_prefix, k.name, k.role, k.rpm_limit, k.daily_limit, k.enabled,
                      k.auto_publish, k.created_at, k.last_used_at, k.owner_user_id, u.username AS owner_username
               FROM api_keys k LEFT JOIN users u ON u.id=k.owner_user_id"""
            + (" WHERE k.owner_user_id=?" if owner_user_id is not None else "")
            + " ORDER BY k.created_at DESC",
            (owner_user_id,) if owner_user_id is not None else (),
        )
        today = date.today().isoformat()
        out = []
        for r in rows:
            used = self.db.scalar(
                "SELECT COUNT(*) FROM usage_log WHERE key_prefix = ? AND day = ?",
                (r["key_prefix"], today),
            )
            d = dict(r)
            d["enabled"] = bool(d["enabled"])
            d["used_today"] = used or 0
            out.append(d)
        return out

    def ensure_bootstrap_admin(self, raw_key: str) -> None:
        """首次部署用环境变量指定一个管理员 key。已存在则忽略。"""
        if not raw_key:
            return
        prefix = _prefix_of(raw_key)
        if self.db.one("SELECT 1 FROM api_keys WHERE key_prefix = ?", (prefix,)):
            return
        with self.db.write() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO api_keys
                   (key_hash, key_prefix, name, role, rpm_limit, daily_limit, enabled, created_at)
                   VALUES (?,?,?,?,?,?,1,?)""",
                (
                    hash_key(raw_key),
                    prefix,
                    "bootstrap-admin",
                    "admin",
                    max(self.default_rpm, 600),
                    max(self.default_daily, 10**9),
                    time.time(),
                ),
            )

    # ---------- 校验 ----------

    def authenticate(self, raw_key: str) -> Principal:
        if not raw_key:
            raise AuthError("缺少 API Key")
        row = self.db.one(
            "SELECT * FROM api_keys WHERE key_hash = ? AND enabled = 1",
            (hash_key(raw_key),),
        )
        if not row:
            raise AuthError("API Key 无效或已吊销")
        role = row["role"]
        if row["owner_user_id"]:
            owner = self.db.one(
                "SELECT role,status FROM users WHERE id=?", (row["owner_user_id"],)
            )
            if not owner or owner["status"] != "approved":
                raise AuthError("Key 所属账号未获批准或已停用")
            if ROLE_RANK.get(role, 0) > ROLE_RANK.get(owner["role"], 0):
                role = owner["role"]
        with self.db.write() as conn:
            conn.execute(
                "UPDATE api_keys SET last_used_at = ? WHERE key_prefix = ?",
                (time.time(), row["key_prefix"]),
            )
        return Principal(
            key_prefix=row["key_prefix"],
            name=row["name"],
            role=role,
            rpm_limit=row["rpm_limit"],
            daily_limit=row["daily_limit"],
            user_id=row["owner_user_id"],
        )

    # ---------- 配额 ----------

    def check_quota(self, p: Principal) -> None:
        now = time.time()
        window = self._rpm_bucket.setdefault(p.key_prefix, [])
        # 滑动 60 秒窗口
        cutoff = now - 60
        window[:] = [t for t in window if t > cutoff]
        if len(window) >= p.rpm_limit:
            retry = max(1, int(60 - (now - window[0])))
            raise QuotaExceeded(
                f"请求过于频繁（{p.rpm_limit} 次/分钟）", retry_after=retry
            )

        today = date.today().isoformat()
        used = (
            self.db.scalar(
                "SELECT COUNT(*) FROM usage_log WHERE key_prefix = ? AND day = ?",
                (p.key_prefix, today),
            )
            or 0
        )
        if used >= p.daily_limit:
            raise QuotaExceeded(
                f"今日调用额度已用尽（{p.daily_limit} 次/天）", retry_after=3600
            )

        window.append(now)

    def log_usage(
        self, p: Principal | None, tool: str, ok: bool, detail: str = ""
    ) -> None:
        prefix = p.key_prefix if p else "-"
        with self.db.write() as conn:
            conn.execute(
                "INSERT INTO usage_log (key_prefix, tool, day, ts, ok, detail) VALUES (?,?,?,?,?,?)",
                (
                    prefix,
                    tool,
                    date.today().isoformat(),
                    time.time(),
                    1 if ok else 0,
                    detail[:300],
                ),
            )

    def usage_summary(self, days: int = 7) -> list[dict]:
        rows = self.db.query(
            """SELECT key_prefix, day, COUNT(*) AS calls,
                      SUM(CASE WHEN ok=0 THEN 1 ELSE 0 END) AS errors
               FROM usage_log GROUP BY key_prefix, day
               ORDER BY day DESC, calls DESC LIMIT ?""",
            (days * 20,),
        )
        return [dict(r) for r in rows]
