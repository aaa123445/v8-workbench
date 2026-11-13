"""SQLite 持久层。

设计取舍：
- 文档正文也存库，不用文件系统。这样备份、迁移、事务一致性都简单，
  2MB 级别的语料完全在 SQLite 的舒适区内。
- 倒排索引不落库，进程启动时从 docs 表全量重建（几十毫秒）。
  语料上到十万级再引入增量索引或外部检索引擎。
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;

-- 知识条目。一条 = 一篇文档。
CREATE TABLE IF NOT EXISTS docs (
    id            TEXT PRIMARY KEY,          -- 稳定 id，如 yuque:210705900
    source        TEXT NOT NULL,             -- yuque | upload | agent | manual
    title         TEXT NOT NULL,
    path_text     TEXT NOT NULL DEFAULT '',  -- 语雀目录路径
    domain        TEXT NOT NULL DEFAULT '',  -- 归一化知识域，如 开发规范/编码规范
    body          TEXT NOT NULL,
    summary       TEXT NOT NULL DEFAULT '',
    words         INTEGER NOT NULL DEFAULT 0,
    url           TEXT NOT NULL DEFAULT '',
    version_hint  TEXT NOT NULL DEFAULT '',  -- 文档内声明的适用版本，如 3.18
    tags          TEXT NOT NULL DEFAULT '[]',
    meta          TEXT NOT NULL DEFAULT '{}',
    checksum      TEXT NOT NULL DEFAULT '',
    created_by    TEXT NOT NULL DEFAULT '',
    created_at    REAL NOT NULL,
    updated_at    REAL NOT NULL,
    is_deprecated INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_docs_domain ON docs(domain);
CREATE INDEX IF NOT EXISTS idx_docs_source ON docs(source);
CREATE INDEX IF NOT EXISTS idx_docs_checksum ON docs(checksum);

-- 全文冗余表，用于 LIKE 兜底检索（倒排召回不足时）
CREATE TABLE IF NOT EXISTS doc_fts (
    id TEXT PRIMARY KEY REFERENCES docs(id) ON DELETE CASCADE,
    text TEXT NOT NULL
);

-- 项目级知识：把零散经验聚成"某客户的某类问题"
CREATE TABLE IF NOT EXISTS projects (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    customer    TEXT NOT NULL DEFAULT '',
    v8_version  TEXT NOT NULL DEFAULT '',
    notes       TEXT NOT NULL DEFAULT '',
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);

-- API Key
CREATE TABLE IF NOT EXISTS api_keys (
    owner_user_id TEXT REFERENCES users(id),
    key_hash    TEXT PRIMARY KEY,
    key_prefix  TEXT NOT NULL,          -- 明文前缀，便于管理员识别
    name        TEXT NOT NULL,
    role        TEXT NOT NULL,          -- admin | writer | reader
    rpm_limit   INTEGER NOT NULL DEFAULT 120,
    daily_limit INTEGER NOT NULL DEFAULT 20000,
    enabled     INTEGER NOT NULL DEFAULT 1,
    created_at  REAL NOT NULL,
    last_used_at REAL NOT NULL DEFAULT 0,
    revoked_at  REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_keys_prefix ON api_keys(key_prefix);

-- 用量流水，按天聚合查询
CREATE TABLE IF NOT EXISTS usage_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    key_prefix  TEXT NOT NULL,
    tool        TEXT NOT NULL,
    day         TEXT NOT NULL,       -- YYYY-MM-DD
    ts          REAL NOT NULL,
    ok          INTEGER NOT NULL DEFAULT 1,
    detail      TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_usage_key_day ON usage_log(key_prefix, day);

-- 变更历史，供审计和回滚
CREATE TABLE IF NOT EXISTS revisions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id      TEXT NOT NULL,
    action      TEXT NOT NULL,       -- create | update | delete
    actor       TEXT NOT NULL DEFAULT '',
    day_at      REAL NOT NULL,
    payload     TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_rev_doc ON revisions(doc_id);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'reader',
    status TEXT NOT NULL DEFAULT 'pending',
    review_note TEXT NOT NULL DEFAULT '',
    reviewed_by TEXT NOT NULL DEFAULT '',
    reviewed_at REAL NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS user_sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id);
CREATE TABLE IF NOT EXISTS auth_attempts (bucket TEXT NOT NULL, at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS idx_auth_attempts ON auth_attempts(bucket, at);
CREATE TABLE IF NOT EXISTS account_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT NOT NULL,
    target_user_id TEXT NOT NULL REFERENCES users(id),
    status TEXT NOT NULL,
    role TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS call_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT REFERENCES users(id),
    key_prefix TEXT NOT NULL,
    credential_kind TEXT NOT NULL,
    credential_name TEXT NOT NULL,
    client TEXT NOT NULL,
    operation TEXT NOT NULL,
    method TEXT NOT NULL,
    path TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    outcome TEXT NOT NULL,
    duration_ms REAL NOT NULL,
    request_summary TEXT NOT NULL,
    result_summary TEXT NOT NULL,
    request_json TEXT NOT NULL,
    response_json TEXT NOT NULL,
    request_truncated INTEGER NOT NULL DEFAULT 0,
    response_truncated INTEGER NOT NULL DEFAULT 0,
    ts REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_calls_user_ts ON call_logs(user_id, ts DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_calls_key_ts ON call_logs(key_prefix, ts DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_calls_ts ON call_logs(ts);

CREATE TABLE IF NOT EXISTS knowledge_audit(id INTEGER PRIMARY KEY AUTOINCREMENT,actor TEXT NOT NULL,action TEXT NOT NULL,target TEXT NOT NULL,details TEXT NOT NULL,created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS categories(id TEXT PRIMARY KEY,name TEXT NOT NULL,parent_id TEXT REFERENCES categories(id),sort_order INTEGER NOT NULL DEFAULT 100,created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS contributions(
 id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,user_id TEXT,key_prefix TEXT NOT NULL,title TEXT NOT NULL,content TEXT NOT NULL,category_id TEXT NOT NULL REFERENCES categories(id),tags TEXT NOT NULL,summary TEXT NOT NULL,source TEXT NOT NULL,target_doc_id TEXT,base_version INTEGER NOT NULL DEFAULT 0,fingerprint TEXT NOT NULL,status TEXT NOT NULL,payload TEXT NOT NULL,quality TEXT NOT NULL,similar TEXT NOT NULL,review_note TEXT NOT NULL DEFAULT '',reviewed_by TEXT NOT NULL DEFAULT '',published_doc_id TEXT,created_at REAL NOT NULL,updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_contributions_owner ON contributions(owner_id,updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_contributions_status ON contributions(status,updated_at DESC);
CREATE TABLE IF NOT EXISTS contribution_events(id INTEGER PRIMARY KEY AUTOINCREMENT,contribution_id TEXT NOT NULL REFERENCES contributions(id),actor TEXT NOT NULL,action TEXT NOT NULL,note TEXT NOT NULL,created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS knowledge_versions(id INTEGER PRIMARY KEY AUTOINCREMENT,doc_id TEXT NOT NULL,version INTEGER NOT NULL,title TEXT NOT NULL,content TEXT NOT NULL,category_id TEXT NOT NULL,tags TEXT NOT NULL,summary TEXT NOT NULL,version_hint TEXT NOT NULL,url TEXT NOT NULL,actor TEXT NOT NULL,created_at REAL NOT NULL,UNIQUE(doc_id,version));
CREATE TABLE IF NOT EXISTS rule_sets(id TEXT PRIMARY KEY,name TEXT NOT NULL,category_id TEXT NOT NULL REFERENCES categories(id),description TEXT NOT NULL,checklist TEXT NOT NULL,doc_ids TEXT NOT NULL,updated_at REAL NOT NULL,actor TEXT NOT NULL);

"""


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._local = threading.local()
        self._write_lock = threading.RLock()
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(api_keys)")}
            if "owner_user_id" not in columns:
                conn.execute(
                    "ALTER TABLE api_keys ADD COLUMN owner_user_id TEXT REFERENCES users(id)"
                )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_keys_owner ON api_keys(owner_user_id)"
            )
            doc_columns = {r[1] for r in conn.execute("PRAGMA table_info(docs)")}
            if "category_id" not in doc_columns:
                conn.execute("ALTER TABLE docs ADD COLUMN category_id TEXT")
            if "knowledge_version" not in doc_columns:
                conn.execute(
                    "ALTER TABLE docs ADD COLUMN knowledge_version INTEGER NOT NULL DEFAULT 1"
                )
            if "auto_publish" not in columns:
                conn.execute(
                    "ALTER TABLE api_keys ADD COLUMN auto_publish INTEGER NOT NULL DEFAULT 0"
                )
            conn.commit()

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.path, check_same_thread=False, timeout=30)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return conn

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = self._conn()
        yield conn

    @contextmanager
    def write(self) -> Iterator[sqlite3.Connection]:
        """写事务。所有写入串行化，避免 SQLite 锁竞争导致的 500。"""
        with self._write_lock:
            conn = self._conn()
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    # ---------- 便捷读取 ----------
    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        return list(self._conn().execute(sql, params))

    def one(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        return self._conn().execute(sql, params).fetchone()

    def scalar(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        row = self.one(sql, params)
        return row[0] if row else None
