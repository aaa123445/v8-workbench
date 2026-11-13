"""服务装配。

全局单例容器。FastAPI、MCP、CLI 三种入口共用同一套 core 实例，
保证行为一致 —— 这是"一套逻辑三种壳"的关键。
"""

from __future__ import annotations

import threading

from .auth import AuthService
from .call_logs import CallLogService
from .accounts import AccountService
from ..config import Settings, get_settings
from .db import Database
from .docs import DocRepo
from .knowledge import KnowledgeService
from .index import SearchIndex


class Container:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.db = Database(self.settings.db_path)
        self.calls = CallLogService(
            self.db,
            self.settings.call_log_retention_days,
            self.settings.call_log_max_entries,
        )
        self.repo = DocRepo(self.db)
        self.index = SearchIndex(self.db)
        self.auth = AuthService(
            self.db,
            require_auth=self.settings.require_auth,
            default_rpm=self.settings.default_rpm,
            default_daily=self.settings.default_daily,
        )
        self.accounts = AccountService(
            self.db, self.settings.default_rpm, self.settings.default_daily
        )
        self.auth.ensure_bootstrap_admin(self.settings.bootstrap_admin_key)
        self._rebuild_lock = threading.Lock()
        self.knowledge = KnowledgeService(self)
        self.index.rebuild()

    def rebuild_index(self) -> int:
        with self._rebuild_lock:
            return self.index.rebuild()


_container: Container | None = None
_lock = threading.Lock()


def get_container() -> Container:
    global _container
    if _container is None:
        with _lock:
            if _container is None:
                _container = Container()
    return _container
