"""SQLite 持久层。

设计取舍：
- 文档正文也存库，不用文件系统。这样备份、迁移、事务一致性都简单，
  2MB 级别的语料完全在 SQLite 的舒适区内。
- 倒排索引不落库，进程启动时从 docs 表全量重建（几十毫秒）。
  语料上到十万级再引入增量索引或外部检索引擎。
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
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
"""


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._local = threading.local()
        self._write_lock = threading.RLock()
        with self.connect() as conn:
            conn.executescript(SCHEMA)

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
