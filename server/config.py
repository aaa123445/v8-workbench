"""工作台配置。全部来自环境变量，便于容器化部署。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env(name: str, default: str) -> str:
    v = os.environ.get(name)
    return v if v not in (None, "") else default


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    return _env(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # 数据目录：SQLite、原始文件、索引快照都放这里
    data_dir: Path = field(default_factory=lambda: Path(_env("V8WB_DATA_DIR", "./data")))
    db_path: Path = field(init=False)
    blob_dir: Path = field(init=False)

    # HTTP 服务
    host: str = field(default_factory=lambda: _env("V8WB_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: _env_int("V8WB_PORT", 8770))
    # 反向代理下的公开地址，用于回给客户端的下一步提示
    public_url: str = field(default_factory=lambda: _env("V8WB_PUBLIC_URL", "http://127.0.0.1:8770"))

    # 鉴权
    require_auth: bool = field(default_factory=lambda: _env_bool("V8WB_REQUIRE_AUTH", True))
    bootstrap_admin_key: str = field(default_factory=lambda: _env("V8WB_BOOTSTRAP_ADMIN_KEY", ""))
    default_rpm: int = field(default_factory=lambda: _env_int("V8WB_DEFAULT_RPM", 120))
    default_daily: int = field(default_factory=lambda: _env_int("V8WB_DEFAULT_DAILY", 20000))

    call_log_retention_days: int = field(default_factory=lambda: _env_int("V8WB_CALL_LOG_RETENTION_DAYS", 30))
    call_log_max_entries: int = field(default_factory=lambda: _env_int("V8WB_CALL_LOG_MAX_ENTRIES", 2000))

    # 检索
    max_top_k: int = field(default_factory=lambda: _env_int("V8WB_MAX_TOP_K", 50))
    max_read_chars: int = field(default_factory=lambda: _env_int("V8WB_MAX_READ_CHARS", 60000))

    # 自动拉取语雀
    yuque_token: str = field(default_factory=lambda: _env("V8WB_YUQUE_TOKEN", ""))
    yuque_book: str = field(default_factory=lambda: _env("V8WB_YUQUE_BOOK", "seeyonkk/v8"))
    yuque_enabled: bool = field(default_factory=lambda: _env_bool("V8WB_YUQUE_ENABLED", False))
    yuque_interval_min: int = field(default_factory=lambda: _env_int("V8WB_YUQUE_INTERVAL_MIN", 1440))

    def __post_init__(self) -> None:
        object.__setattr__(self, "db_path", self.data_dir / "v8wb.sqlite3")
        object.__setattr__(self, "blob_dir", self.data_dir / "blobs")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.blob_dir.mkdir(parents=True, exist_ok=True)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
