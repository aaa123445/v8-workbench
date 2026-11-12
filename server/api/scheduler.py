"""语雀知识库定时同步。

用最朴素的后台线程轮询，不引 APScheduler。理由：只有一个定时任务，
依赖越少越不容易在客户服务器上出问题。

启动时如果上次同步距今超过间隔，会先补一次 —— 避免容器频繁重启时一直不跑。
"""

from __future__ import annotations

import threading
import time

from ..core.container import Container
from ..core.yuque import sync_book

_last_run: dict[str, float] = {"ts": 0.0, "ok": 0, "failed": 0}
_lock = threading.Lock()


def state() -> dict:
    with _lock:
        return dict(_last_run)


def _should_run(interval_sec: int) -> bool:
    with _lock:
        return time.time() - _last_run["ts"] >= interval_sec


def _record(stat: dict) -> None:
    with _lock:
        _last_run["ts"] = time.time()
        _last_run["ok"] = stat.get("created", 0) + stat.get("updated", 0)
        _last_run["failed"] = stat.get("failed", 0)


def run_once(c: Container, *, force: bool = False, actor: str = "scheduler") -> dict:
    s = c.settings
    if not s.yuque_book:
        return {"skipped": True, "reason": "未配置语雀知识库"}
    try:
        stat = sync_book(c.repo, s.yuque_book, token=s.yuque_token, force=force, actor=actor)
        if stat.get("created") or stat.get("updated"):
            c.rebuild_index()
        _record(stat)
        return stat
    except Exception as e:  # noqa: BLE001
        with _lock:
            _last_run["ts"] = time.time()
            _last_run["failed"] = -1
        return {"error": str(e)[:300]}


def start_background(c: Container) -> threading.Thread | None:
    """启动后台同步线程。未启用时返回 None。"""
    s = c.settings
    if not s.yuque_enabled or not s.yuque_book:
        return None

    interval = max(5, s.yuque_interval_min) * 60

    def loop() -> None:
        # 启动即判断：上次跑太久就直接补一次
        while True:
            if _should_run(interval):
                run_once(c)
            # 每 5 分钟醒一次检查，不用 sleep 整个间隔以免改配置后要重启
            time.sleep(300)

    t = threading.Thread(target=loop, name="yuque-sync", daemon=True)
    t.start()
    return t
