#!/usr/bin/env python3
"""V8 客开工作台 CLI。

面向三类使用者：
  1. 人（运维/开发）：wb search / wb read / wb rules
  2. 自研 agent（dsh 等）：wb --json 输出结构化结果，便于程序解析
  3. CI/脚本：wb push 批量推送知识、wb sync 触发同步

设计上 CLI 和 MCP 走同一套 HTTP 接口，行为保证一致。
区别是 CLI 多了本地批量操作（push/import）和运维动作（key 管理、同步）。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

try:
    import httpx
except ImportError:
    print("需要安装依赖：pip install httpx", file=sys.stderr)
    sys.exit(1)

DEFAULT_URL = os.environ.get("V8WB_URL", "http://127.0.0.1:8770").rstrip("/")
DEFAULT_KEY = os.environ.get("V8WB_KEY", "")

GREEN, YELLOW, RED, DIM, BOLD, RESET = "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[1m", "\033[0m"


def _color(s: str, c: str, enabled: bool) -> str:
    return f"{c}{s}{RESET}" if enabled else s


class Client:
    def __init__(self, url: str, key: str, *, timeout: float = 60.0) -> None:
        self.url = url.rstrip("/")
        self.key = key
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.key:
            h["Authorization"] = f"Bearer {self.key}"
        return h

    def call(self, method: str, path: str, payload: Any = None) -> Any:
        try:
            with httpx.Client(timeout=self.timeout) as c:
                r = c.request(method, f"{self.url}{path}", json=payload, headers=self._headers())
        except httpx.ConnectError:
            _die(f"连不上工作台 {self.url}。用 --url 指定地址，或确认服务已启动。")
        except httpx.TimeoutException:
            _die(f"请求超时（{self.timeout}s）：{path}")
        if r.status_code == 401:
            _die("API Key 无效。用 --key 或环境变量 V8WB_KEY 指定，或向管理员申请。")
        if r.status_code == 403:
            _die(f"权限不足：{_errmsg(r)}")
        if r.status_code == 429:
            _die(f"调用额度超限：{_errmsg(r)}")
        if r.status_code >= 400:
            _die(f"请求失败 {r.status_code}：{_errmsg(r)}")
        return r.json()


def _errmsg(r: httpx.Response) -> str:
    try:
        d = r.json()
        if isinstance(d, dict):
            detail = d.get("detail") or d
            if isinstance(detail, dict):
                msg = detail.get("message") or detail.get("error") or ""
                hint = detail.get("hint") or ""
                return f"{msg}{('  → ' + hint) if hint else ''}"
            return str(detail)
        return str(d)
    except Exception:
        return r.text[:300]


def _die(msg: str) -> None:
    print(f"{RED}错误{RESET} {msg}", file=sys.stderr)
    sys.exit(1)


def _emit(data: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))


# ---------------- 命令 ----------------

def cmd_search(c: Client, a) -> None:
    out = c.call(
        "POST", "/api/v1/search",
        {"query": a.query, "limit": a.limit, "domain": a.domain, "tag": a.tag},
    )
    if a.json:
        _emit(out, True)
        return
    items = out.get("results", [])
    if not items:
        print(f"未检到「{a.query}」")
        if out.get("hint"):
            print(_color(out["hint"], DIM, sys.stdout.isatty()))
        return
    print(f"{BOLD}检索「{a.query}」命中 {len(items)} 篇{RESET}\n")
    for i, r in enumerate(items, 1):
        print(f"{GREEN}{i}.{RESET} {BOLD}{r['title']}{RESET}  {DIM}{r['id']}{RESET}")
        if r.get("path"):
            print(f"   {DIM}{r['path']}{RESET}")
        meta = []
        if r.get("matched_terms"):
            meta.append("命中 " + "、".join(r["matched_terms"][:6]))
        if r.get("version_hint"):
            meta.append("版本 " + r["version_hint"])
        if meta:
            print(f"   {DIM}{'  |  '.join(meta)}{RESET}")
        print()
    if out.get("hint"):
        print(_color(out["hint"], YELLOW, sys.stdout.isatty()))


def cmd_read(c: Client, a) -> None:
    out = c.call("POST", "/api/v1/read", {"id": a.id, "title": a.title, "offset": a.offset, "max_chars": a.max_chars})
    if a.json:
        _emit(out, True)
        return
    if out.get("ambiguous"):
        print("标题匹配多篇，请用 id：")
        for x in out["candidates"]:
            print(f"  {x['id']}  {x['title']}  ({x['path']})")
        return
    if not a.raw:
        print(_color(f"# {out['title']}", BOLD, True))
        print(_color(f"{out.get('path') or '-'}  |  {out.get('source')}  |  {out.get('url') or '-'}", DIM, True))
        print("─" * 60)
    print(out["content"])
    if out.get("truncated"):
        print(f"\n{DIM}[共 {out['total_chars']} 字，用 --offset {out['next_offset']} 继续]{RESET}")


def cmd_rules(c: Client, a) -> None:
    out = c.call("POST", "/api/v1/rules", {"task": a.task, "include_docs": a.docs})
    if a.json:
        _emit(out, True)
        return
    print(out.get("brief", ""))
    idx = out.get("documents_index") or []
    if idx and not a.docs:
        print(f"\n{BOLD}对应文档 id{RESET}（用 wb read <id> 展开）")
        for d in idx:
            print(f"  {DIM}{d['id']}{RESET}  {d['title']}  {DIM}({d['chars']} 字){RESET}")


def cmd_domains(c: Client, a) -> None:
    out = c.call("GET", "/api/v1/domains")
    if a.json:
        _emit(out, True)
        return
    print(f"{BOLD}知识域{RESET}\n")
    for d in out.get("domains", []):
        print(f"  {d['domain']:<20} {d['count']:>4} 篇")
    print(f"\n共 {out.get('total', 0)} 篇")


def cmd_stats(c: Client, a) -> None:
    out = c.call("GET", "/api/v1/stats")
    if a.json:
        _emit(out, True)
        return
    print(f"文档 {out.get('documents')}  词条 {out.get('terms')}  平均长度 {out.get('avg_body_len')}\n")
    print(f"{BOLD}知识域{RESET}")
    for k, v in (out.get("by_domain") or {}).items():
        print(f"  {k:<22} {v:>4}")
    print(f"\n{BOLD}来源{RESET}")
    for k, v in (out.get("by_source") or {}).items():
        print(f"  {k:<22} {v:>4}")


def cmd_push(c: Client, a) -> None:
    """把本地 Markdown/JSON 文件推送到知识库。

    支持两种输入：
      - 单个 .md 文件：文件名当标题，正文当内容
      - 目录：递归收集 .md
      - .json：数组，每项含 title/content/path/tags
    """
    target = Path(a.path)
    if not target.exists():
        _die(f"路径不存在：{target}")

    items: list[dict] = []
    if target.is_file() and target.suffix.lower() == ".json":
        data = json.loads(target.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = [data]
        for d in data:
            items.append({**d, "source": d.get("source", "agent")})
    else:
        files = [target] if target.is_file() else sorted(target.rglob("*.md"))
        for f in files:
            if f.name.startswith("."):
                continue
            body = f.read_text(encoding="utf-8", errors="replace")
            title = a.title if (a.title and len(files) == 1) else _title_from_md(f, body)
            items.append(
                {
                    "title": title,
                    "content": body,
                    "path": a.kb_path or "",
                    "project": a.project,
                    "tags": [t.strip() for t in a.tags.split(",") if t.strip()],
                    "source": "agent",
                }
            )

    if not items:
        _die("没有找到可推送的内容")

    if not a.yes:
        print(f"即将推送 {len(items)} 条到 {c.url}")
        for it in items[:10]:
            print(f"  - {it['title']}")
        if len(items) > 10:
            print(f"  ... 另有 {len(items) - 10} 条")
        if input("继续？[y/N] ").strip().lower() != "y":
            print("已取消")
            return

    ok = 0
    failed = []
    # 分批，避免单次请求过大
    for i in range(0, len(items), 20):
        chunk = items[i : i + 20]
        out = c.call("POST", "/api/v1/knowledge/batch", chunk)
        ok += out.get("count", 0)
        failed.extend(out.get("failed", []))

    print(f"{GREEN}成功 {ok}{RESET} 条，失败 {len(failed)} 条")
    for f in failed:
        print(f"  {RED}✗{RESET} {f['title']}: {f['error']}")


def _title_from_md(p: Path, body: str) -> str:
    for line in body.split("\n"):
        s = line.strip()
        if s.startswith("# "):
            return s[2:].strip()[:120]
    return p.stem


def cmd_sync(c: Client, a) -> None:
    q = []
    if a.force:
        q.append("force=true")
    if a.limit:
        q.append(f"limit={a.limit}")
    qs = ("?" + "&".join(q)) if q else ""
    print("开始同步语雀知识库…（全量首次约 1-3 分钟）")
    out = c.call("POST", f"/api/v1/admin/sync/yuque{qs}")
    if a.json:
        _emit(out, True)
        return
    print(f"目录节点 {out.get('toc')}  实抓 {out.get('fetched')}")
    print(f"新增 {out.get('created')}  更新 {out.get('updated')}  "
          f"未变 {out.get('unchanged')}  跳过 {out.get('skipped')}  失败 {out.get('failed')}")
    for e in (out.get("errors") or [])[:10]:
        print(f"  {RED}✗{RESET} {e['title']}: {e['error']}")


def cmd_key(c: Client, a) -> None:
    if a.action == "create":
        out = c.call(
            "POST", "/api/v1/admin/keys",
            {"name": a.name, "role": a.role, "rpm": a.rpm, "daily": a.daily},
        )
        print(f"{GREEN}已创建{RESET}  {out['name']}  role={out['role']}  prefix={out['prefix']}")
        print(f"\n{BOLD}{out['key']}{RESET}\n")
        print(_color("此 key 只显示一次，请立即保存", YELLOW, True))
    elif a.action == "list":
        out = c.call("GET", "/api/v1/admin/keys")
        if a.json:
            _emit(out, True)
            return
        for k in out.get("keys", []):
            icon = f"{GREEN}●{RESET}" if k["enabled"] else f"{RED}○{RESET}"
            print(f"{icon} {k['key_prefix']:<14} {k['role']:<7} {k['name']:<20} 今日 {k['used_today']}/{k['daily_limit']}")
    elif a.action == "revoke":
        out = c.call("DELETE", f"/api/v1/admin/keys/{a.prefix}")
        print("已吊销" if out.get("revoked") else "未找到该 key")


def cmd_health(c: Client, a) -> None:
    out = c.call("GET", "/health")
    if a.json:
        _emit(out, True)
        return
    print(f"{GREEN}●{RESET} 工作台正常  {c.url}")
    print(f"  版本 {out.get('version')}  文档 {out.get('documents')} 篇")


def cmd_serve(a) -> None:
    """本地起 HTTP 服务（通常由 systemd/docker 调用，这里方便调试）。"""
    import uvicorn

    from server.config import get_settings

    s = get_settings()
    uvicorn.run("server.api.http_app:app", host=a.host or s.host, port=a.port or s.port, log_level=a.log_level)


def cmd_mcp(a) -> None:
    """启动 MCP stdio 服务。"""
    os.environ["V8WB_URL"] = a.url or DEFAULT_URL
    if a.key:
        os.environ["V8WB_KEY"] = a.key
    if a.local:
        os.environ["V8WB_MODE"] = "local"
    from server.api.mcp_server import main as mcp_main

    mcp_main()


# ---------------- 参数 ----------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="wb",
        description="V8 客开工作台 CLI — 知识检索、规范查阅、经验沉淀",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""常用示例:
  wb search "组织同步 中间表"
  wb rules spi --docs
  wb read yuque:210705900
  wb push ./notes --project 某客户 --tags "UDC,前端"
  wb sync --force
""",
    )
    p.add_argument("--url", default=DEFAULT_URL, help=f"服务地址（默认 {DEFAULT_URL}）")
    p.add_argument("--key", default=DEFAULT_KEY, help="API Key（或环境变量 V8WB_KEY）")
    p.add_argument("--json", action="store_true", help="输出 JSON，便于脚本/agent 解析")
    p.add_argument("--timeout", type=float, default=60.0, help="请求超时秒数")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="检索知识库")
    s.add_argument("query")
    s.add_argument("-n", "--limit", type=int, default=8)
    s.add_argument("-d", "--domain", default="")
    s.add_argument("-t", "--tag", default="")
    s.set_defaults(func=cmd_search, needs_client=True)

    r = sub.add_parser("read", help="读取文档正文")
    r.add_argument("id", nargs="?", default="")
    r.add_argument("--title", default="")
    r.add_argument("--offset", type=int, default=0)
    r.add_argument("--max-chars", type=int, default=None)
    r.add_argument("--raw", action="store_true", help="不打印头部元信息")
    r.set_defaults(func=cmd_read, needs_client=True)

    ru = sub.add_parser("rules", help="获取任务规范清单")
    ru.add_argument("task", nargs="?", default="", help="spi/udc/bpm/frontend/integration/data/docs/general")
    ru.add_argument("--docs", action="store_true", help="附带规范正文")
    ru.set_defaults(func=cmd_rules, needs_client=True)

    d = sub.add_parser("domains", help="列出知识域")
    d.set_defaults(func=cmd_domains, needs_client=True)

    st = sub.add_parser("stats", help="知识库统计")
    st.set_defaults(func=cmd_stats, needs_client=True)

    push = sub.add_parser("push", help="推送本地知识文件")
    push.add_argument("path", help=".md 文件 / 目录 / .json")
    push.add_argument("--title", default="", help="单文件时指定标题")
    push.add_argument("--path-tag", dest="kb_path", default="", help="知识库内路径，如 沉淀/某项目")
    push.add_argument("--project", default="")
    push.add_argument("--tags", default="")
    push.add_argument("-y", "--yes", action="store_true", help="跳过确认")
    push.set_defaults(func=cmd_push, needs_client=True)

    sy = sub.add_parser("sync", help="同步语雀知识库（管理员）")
    sy.add_argument("--force", action="store_true", help="忽略增量判断，全量重抓")
    sy.add_argument("--limit", type=int, default=None, help="最多抓取 N 篇，调试用")
    sy.set_defaults(func=cmd_sync, needs_client=True)

    k = sub.add_parser("key", help="API Key 管理（管理员）")
    k.add_argument("action", choices=["create", "list", "revoke"])
    k.add_argument("name", nargs="?", default="")
    k.add_argument("--role", default="reader", choices=["reader", "writer", "admin"])
    k.add_argument("--rpm", type=int, default=None)
    k.add_argument("--daily", type=int, default=None)
    k.add_argument("--prefix", default="")
    k.set_defaults(func=cmd_key, needs_client=True)

    h = sub.add_parser("health", help="健康检查")
    h.set_defaults(func=cmd_health, needs_client=True)

    sv = sub.add_parser("serve", help="启动 HTTP 服务")
    sv.add_argument("--host", default="")
    sv.add_argument("--port", type=int, default=0)
    sv.add_argument("--log-level", default="info")
    sv.set_defaults(func=None, needs_client=False, serve=True)

    m = sub.add_parser("mcp", help="启动 MCP stdio 服务")
    m.add_argument("--local", action="store_true", help="本地模式，直接读本地库")
    m.set_defaults(func=None, needs_client=False, mcp=True)

    return p


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    a = parser.parse_args(argv)

    if getattr(a, "serve", False):
        cmd_serve(a)
        return
    if getattr(a, "mcp", False):
        cmd_mcp(a)
        return

    client = Client(a.url, a.key, timeout=a.timeout)
    a.func(client, a)


if __name__ == "__main__":
    main()
