"""MCP 入口。

两种运行模式：

  proxy  （默认，推荐）本地 stdio 进程，每个工具调用转发到云端 HTTP。
         好处：云端集中管知识、管 key、管配额；本地只装一个薄壳。
         配置：V8WB_URL + V8WB_KEY 环境变量。

  local  直接读本地 data 目录，完全离线。
         适合没网/想先试用的场景，配置 V8WB_DATA_DIR。

工具设计原则：
  - 描述里写清"什么时候用"，不只写"是什么"。模型靠描述决定是否调用。
  - 返回结构化短文本 + 明确下一步指引，减少模型瞎猜。
  - kb_* 提供通用入口，v8_* 保留旧客户端兼容。
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

try:
    # MCP SDK 2.x 把 FastMCP 改名成 MCPServer；1.x 兼容走 FastMCP
    from mcp.server.mcpserver import MCPServer
except ImportError:  # pragma: no cover
    try:
        from mcp.server.fastmcp import FastMCP as MCPServer  # type: ignore
    except ImportError:
        print("需要安装 mcp 包：pip install 'mcp>=1.2'", file=sys.stderr)
        raise

MODE = os.environ.get("V8WB_MODE", "proxy").strip().lower()
BASE_URL = (
    os.environ.get("TEAMKB_URL") or os.environ.get("V8WB_URL", "http://127.0.0.1:8770")
).rstrip("/")
API_KEY = os.environ.get("TEAMKB_KEY") or os.environ.get("V8WB_KEY", "")

INSTRUCTIONS = """团队知识库：开始任务时用 kb_categories / kb_rules 找到分类与团队规范，
用 kb_search 检索，再用 kb_read 核对原文。完成任务后，只提交经过实际验证、
具有复用价值且已经脱敏的解决方案，使用 kb_propose 进入审核。
更新已有知识时传 target_doc_id。不要上传完整会话、仓库或凭据。
v8_* 工具保留用于兼容旧的致远 V8 工作流。"""

mcp = MCPServer(
    "team-knowledge",
    instructions=INSTRUCTIONS,
    version="0.5.0",
)


# ---------------- 后端抽象 ----------------


def _remote(path: str, payload: dict | None = None, *, method: str = "POST") -> Any:
    import httpx

    headers = {"Content-Type": "application/json", "X-V8WB-Client": "mcp"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    url = f"{BASE_URL}{path}"
    try:
        with httpx.Client(timeout=60.0) as client:
            r = client.request(method, url, json=payload, headers=headers)
    except httpx.ConnectError as e:
        raise RuntimeError(
            f"连不上工作台 {BASE_URL}。请确认服务器已启动，或检查 V8WB_URL 配置。详情：{e}"
        ) from e
    if r.status_code == 401:
        raise RuntimeError("API Key 无效或已过期，请检查 V8WB_KEY 环境变量")
    if r.status_code == 429:
        raise RuntimeError(f"调用额度超限：{r.text[:200]}")
    if r.status_code >= 400:
        raise RuntimeError(f"工作台返回 {r.status_code}：{r.text[:300]}")
    return r.json()


def _local():
    from server.core.container import get_container
    from server.core.service import WorkbenchService

    return WorkbenchService(get_container())


def _call(
    path: str,
    payload: dict | None = None,
    *,
    method: str = "POST",
    local_fn: str | None = None,
    local_args: dict | None = None,
) -> Any:
    if MODE == "local":
        svc = _local()
        fn = getattr(svc, local_fn or path.strip("/").split("/")[-1])
        return fn(**(local_args if local_args is not None else (payload or {})))
    return _remote(path, payload, method=method)


# ---------------- 工具 ----------------


@mcp.tool()
def v8_search(
    query: str,
    limit: int = 8,
    domain: str = "",
    tag: str = "",
) -> str:
    """检索致远 V8 客开知识库。

    【什么时候用】在动手写 V8 客开代码之前，或不确定某个平台能力/扩展点怎么用时。
    凡是涉及 SPI 扩展、UDC、BPM、集成平台、组织/待办同步、单点登录、前端扩展、
    组件用法、Nacos/MQ/缓存/Mybatis 等平台组件的问题，都应该先调这个工具，
    不要凭记忆写 V8 的 API —— 平台接口在不同版本差异很大。

    【query 怎么写】用平台术语，不要用口语。
      好：「组织同步 中间表」「SPI扩展 登录」「@seeyon/global 请求封装」
      差：「怎么把用户同步过来」「登录那块怎么改」
    如果第一次没查到，换一组更短的术语重试，不要放弃。

    【参数】
      query   检索词，中文关键词或平台术语均可
      limit   返回条数，默认 8
      domain  可选，按知识域过滤。常用：开发规范 / 扩展能力 / 集成平台 / UDC平台 /
              BPM平台 / 开发文档 / 移动端开发 / 门户平台
      tag     可选，按标签过滤，如 SPI扩展 / UDC / 组织同步 / 单点登录 / 前端

    【返回】文档列表，每条含 id、title、path（语雀目录路径）、score、matched_terms。
    命中后**必须**用 v8_read 打开最相关的 1-2 篇确认细节，不要只看摘要就动手。
    """
    out = _call(
        "/api/v1/search",
        {"query": query, "limit": limit, "domain": domain, "tag": tag},
        local_fn="search",
    )
    return _format_search(out)


@mcp.tool()
def v8_read(doc_id: str = "", title: str = "", offset: int = 0) -> str:
    """读取一篇 V8 客开文档的完整正文。

    【什么时候用】v8_search 拿到结果后，用来展开最相关的文档。
    写涉及平台 API 的代码前，务必先读完对应文档，确认接口签名和配置方式。

    【参数】
      doc_id  从 v8_search 结果里取 id，最可靠
      title   也可以用标题读；若标题匹配多篇会返回候选列表让你选
      offset  正文很长时用于分段读取，从上次返回的 next_offset 继续

    【返回】Markdown 正文。末尾若提示 truncated，用 next_offset 继续读。
    """
    out = _call(
        "/api/v1/read",
        {"id": doc_id, "title": title, "offset": offset},
        local_fn="read",
        local_args={"doc_id": doc_id, "title": title, "offset": offset},
    )
    if out.get("ambiguous"):
        cands = "\n".join(
            f"  - {c['id']}  {c['title']}  ({c['path']})" for c in out["candidates"]
        )
        return f"标题匹配到多篇，请用 id 重新调用：\n{cands}"
    head = (
        f"# {out['title']}\n"
        f"- id: {out['id']}\n"
        f"- 目录: {out.get('path') or '-'}\n"
        f"- 来源: {out.get('source')}  版本提示: {out.get('version_hint') or '未标注'}\n"
        f"- 原文: {out.get('url') or '-'}\n\n---\n\n"
    )
    tail = ""
    if out.get("truncated"):
        tail = f"\n\n---\n[正文共 {out['total_chars']} 字，已显示至 {out['next_offset']}。用 offset={out['next_offset']} 继续读取]"
    return head + out["content"] + tail


@mcp.tool()
def v8_rules(task: str = "", include_docs: bool = False) -> str:
    """获取某类 V8 客开任务必须遵守的开发规范清单与自查项。

    【什么时候用】开始一个 V8 客开任务时**第一件事**就该调这个。
    它把散落在语雀里的规范文档，按任务类型编排成一份可执行清单：
    必读规范 + 相关扩展点 + 提交前自查项 + 常见坑。

    比一篇篇 v8_search 规范文档高效得多，且不会漏项。

    【参数】
      task         任务类型或自然语言描述。取值：spi / udc / bpm / frontend /
                   integration / data / docs / general，也可以直接写描述如
                   「前端自定义门户元素」「给客户做组织同步」
      include_docs 是否直接附带规范正文（默认 false，只给清单和文档 id）。
                   规范正文加起来很长，建议先看清单，需要时再用 v8_read 精确展开。

    【返回】任务画像 + 必读规范标题与 id + 自查清单 + 常见坑（Markdown）
    """
    out = _call(
        "/api/v1/rules",
        {"task": task, "include_docs": include_docs},
        local_fn="rules",
    )
    return _format_rules(out)


@mcp.tool()
def v8_domains() -> str:
    """列出知识库的全部知识域及文档数量。

    【什么时候用】v8_search 多次没查到、或不确定该往哪个方向找时，
    先看这里有哪些知识域，再决定用 domain 参数定向检索。
    """
    out = _call("/api/v1/domains", {}, method="GET", local_fn="domains")
    lines = ["# V8 客开知识库知识域", ""]
    for d in out.get("domains", []):
        lines.append(f"- **{d['domain']}** — {d['count']} 篇")
    lines.append(f"\n共 {out.get('total', 0)} 篇")
    return "\n".join(lines)


@mcp.tool()
def v8_contribute(
    title: str,
    content: str,
    project: str = "",
    tags: str = "",
    summary: str = "",
) -> str:
    """把这次开发中获得的、可复用的 V8 客开经验沉淀进工作台知识库。

    【什么时候用】完成一个客开需求后，如果碰到了以下任一情况，应该主动沉淀：
      - 文档里没写清、靠试错才搞明白的平台行为
      - 踩到的坑和最终解法（尤其是报错信息 + 根因 + 修复）
      - 客户特定的配置组合（脱敏后）
      - 一段可复用的代码骨架

    **不要沉淀**：客户敏感信息（账号、密码、内网地址、真实人员数据）、
    平台文档原文（知识库里已有）、一次性的临时调试过程。

    【怎么写】content 用 Markdown，建议结构：
      ## 场景      什么需求下会遇到
      ## 现象      报错信息 / 异常表现
      ## 根因      为什么
      ## 解法      具体怎么改，带关键代码
      ## 适用版本  在哪个 V8 版本验证过

    一条知识要能脱离上下文独立看懂 —— 半年后别人（或你自己）搜到它要能直接用。

    【参数】
      title    一句话标题，包含关键词便于以后检索，如「UDC 自定义页面取当前用户为空」
      content  Markdown 正文，至少 20 字
      project  可选，项目/客户名（脱敏）
      tags     可选，逗号分隔，如「UDC,前端」
      summary  可选，一句话摘要

    【返回】入库结果，含 doc_id
    """
    payload = {
        "title": title,
        "content": content,
        "project": project,
        "summary": summary,
        "tags": [t.strip() for t in tags.split(",") if t.strip()],
        "source": "manual",
    }
    out = _generic("/api/v1/contributions", payload)
    return json.dumps(out, ensure_ascii=False)


@mcp.tool()
def v8_stats() -> str:
    """查看工作台知识库规模和分类分布。用于确认知识库是否健康、内容缺口在哪。"""
    out = _call("/api/v1/stats", {}, method="GET", local_fn="stats")
    lines = [
        f"文档总数：{out.get('documents', 0)}",
        f"索引词条：{out.get('terms', 0)}",
        "",
        "## 按知识域",
    ]
    for k, v in (out.get("by_domain") or {}).items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## 按来源")
    for k, v in (out.get("by_source") or {}).items():
        lines.append(f"- {k}: {v}")
    return "\n".join(lines)


# Generic tools return structured JSON and use the same review pipeline.
def _generic(path, payload=None, method="POST"):
    if MODE != "local":
        return _remote(path, payload, method=method)
    from server.core.auth import Principal

    k = _local().c.knowledge
    if path == "/api/v1/categories":
        return {"categories": k.categories()}
    if path == "/api/v1/standards":
        return {"standards": k.standards((payload or {}).get("category_id", ""))}
    if path == "/api/v1/contributions":
        p = Principal("local-agent", "Offline agent", "writer", 100000, 100000)
        return k.propose(p, payload)
    raise RuntimeError("此工具仅支持 proxy 模式")


@mcp.tool()
def kb_categories() -> str:
    """列出团队知识分类树、分类 ID 和文档数量。检索或提交前用于确定分类。"""
    return json.dumps(_generic("/api/v1/categories", method="GET"), ensure_ascii=False)


@mcp.tool()
def kb_search(query: str, category_id: str = "", tag: str = "", limit: int = 8) -> str:
    """按关键词、分类（包含子分类）和标签检索已发布知识。结果需用 kb_read 核对。"""
    return json.dumps(
        _call(
            "/api/v1/search",
            {"query": query, "category_id": category_id, "tag": tag, "limit": limit},
            local_fn="search",
        ),
        ensure_ascii=False,
    )


@mcp.tool()
def kb_read(doc_id: str, offset: int = 0) -> str:
    """读取已发布文档，包含分类和版本。truncated 时用 next_offset 继续读取。"""
    return json.dumps(
        _call(
            "/api/v1/read",
            {"id": doc_id, "offset": offset},
            local_fn="read",
            local_args={"doc_id": doc_id, "offset": offset},
        ),
        ensure_ascii=False,
    )


@mcp.tool()
def kb_rules(category_id: str = "") -> str:
    """获取管理员配置的团队规范清单和关联文档 ID。开始任务时调用。"""
    if MODE == "local":
        return json.dumps(
            {"standards": _local().c.knowledge.standards(category_id)},
            ensure_ascii=False,
        )
    from urllib.parse import urlencode

    return json.dumps(
        _remote(
            "/api/v1/standards?" + urlencode({"category_id": category_id}), method="GET"
        ),
        ensure_ascii=False,
    )


@mcp.tool()
def kb_propose(
    title: str,
    content: str,
    category_id: str,
    problem: str,
    solution: str,
    verification: str,
    limitations: str,
    verified: bool = False,
    reusable: bool = False,
    tags: list[str] | None = None,
    target_doc_id: str = "",
    base_version: int | None = None,
) -> str:
    """提交已实际验证且可复用的脱敏方案，默认待管理员审核。
    必须说明问题、具体解法、真实验证证据和适用限制。未验证时不要编造证据。
    先搜索避免重复；修正现有文档传 target_doc_id 和读取时的 knowledge_version 作为 base_version。不会直接覆盖线上文档。
    """
    payload = dict(
        title=title,
        content=content,
        category_id=category_id,
        problem=problem,
        solution=solution,
        verification=verification,
        limitations=limitations,
        verified=verified,
        reusable=reusable,
        tags=tags or [],
        target_doc_id=target_doc_id,
        base_version=base_version,
        source="agent",
    )
    return json.dumps(_generic("/api/v1/contributions", payload), ensure_ascii=False)


@mcp.tool()
def kb_contributions(contribution_id: str = "") -> str:
    """查看自己的贡献状态和审核意见；传贡献 ID 获取详情。"""
    if MODE == "local":
        raise RuntimeError("请在本地网页查看离线候选；团队审核需要 proxy 模式")
    from urllib.parse import quote

    return json.dumps(
        _remote(
            "/api/v1/contributions"
            + ("/" + quote(contribution_id, safe="") if contribution_id else ""),
            method="GET",
        ),
        ensure_ascii=False,
    )


# ---------------- 格式化 ----------------


def _format_search(out: dict) -> str:
    items = out.get("results", [])
    if not items:
        return f"未检到「{out.get('query')}」。\n{out.get('hint', '')}"

    lines = [f"检索「{out.get('query')}」命中 {len(items)} 篇：", ""]
    for i, r in enumerate(items, 1):
        terms = "、".join(r.get("matched_terms", [])[:6])
        lines.append(f"**{i}. {r['title']}**  `{r['id']}`")
        if r.get("path"):
            lines.append(f"   目录：{r['path']}")
        line = f"   命中：{terms}"
        if r.get("version_hint"):
            line += f"   版本：{r['version_hint']}"
        lines.append(line)
    if out.get("hint"):
        lines.append("")
        lines.append(f"> {out['hint']}")
    lines.append("")
    lines.append("下一步：用 v8_read 打开最相关的文档确认细节后再动手。")
    return "\n".join(lines)


def _format_rules(out: dict) -> str:
    return out.get("brief") or json.dumps(out, ensure_ascii=False, indent=2)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
