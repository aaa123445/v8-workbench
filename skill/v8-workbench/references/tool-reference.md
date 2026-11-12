# 工具参考

工作台提供三种形态，能力边界不同，选错形态会白费力气。

## 三种形态的分工

| 形态 | 适合什么 | 不适合什么 |
|---|---|---|
| **MCP** | agent 自主决定何时查、查什么。Claude Code / Codex 自动发现工具 | 批量操作、CI 脚本、运维 |
| **CLI** | 人工命令、脚本化、批量推送、管理操作 | — |
| **Skill** | 定义"什么时候用什么工具、查到后怎么落地" | 不含任何服务端逻辑 |

关键：**MCP 只提供"能查"，Skill 提供"该查什么"**。只接 MCP 不装 Skill，agent 往往放着工具不用，或者查一次就停下。

## MCP 工具

配置后在 agent 的工具列表里直接可见。

### `v8_search`

检索 V8 客开知识库。

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `query` | string | 必填 | 检索词，用平台术语 |
| `limit` | int | 8 | 返回条数 |
| `domain` | string | "" | 知识域过滤 |
| `tag` | string | "" | 标签过滤 |

返回：文档列表，每条含 `id` / `title` / `path` / `score` / `matched_terms` / `reasons`。

`reasons` 说明为什么这条排在这里（`标题高度相关` / `覆盖全部查询词`），可以用来判断是否可信。

### `v8_read`

读文档全文。

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `doc_id` | string | "" | 从 search 结果取，最可靠 |
| `title` | string | "" | 按标题读，匹配多篇会返回候选 |
| `offset` | int | 0 | 长文分段读取 |

返回头部元信息 + Markdown 正文。`truncated=true` 时用 `next_offset` 继续。

### `v8_rules`

按任务类型返回规范清单。

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `task` | string | "" | `spi`/`udc`/`bpm`/`frontend`/`integration`/`data`/`docs`/`general`，或自然语言描述 |
| `include_docs` | bool | false | 是否附带规范正文。默认 false，只给清单和 id |

返回：必读规范标题 + 文档 id + 自查清单 + 常见坑。**只带了 id 不带正文**，因为规范正文全展开会占满上下文 —— 需要时再 `v8_read`。

### `v8_domains`

列出知识域和文档数。用于 search 多次失败后换方向。

### `v8_contribute`

沉淀经验。

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `title` | string | 必填 | 含关键词的一句话 |
| `content` | string | 必填 | Markdown，≥20 字 |
| `project` | string | "" | 项目名（脱敏） |
| `tags` | string | "" | 逗号分隔 |
| `summary` | string | "" | 一句话摘要 |

### `v8_stats`

知识库规模与分布。

## CLI 命令

CLI 与 MCP 共用同一套 HTTP 接口，结果一致。额外提供 MCP 没有的批量和管理能力。

```bash
# 全局参数（所有子命令通用）
wb --url http://server:8770 --key wb_xx_yyy --json <command>
```

环境变量 `V8WB_URL` / `V8WB_KEY` 可替代 `--url` / `--key`。

### 检索类

```bash
wb search "组织同步 中间表" -n 5 -d 集成平台
wb read yuque:224228683
wb read --title "接口规范"
wb read yuque:224228683 --offset 6000
wb rules spi
wb rules frontend --docs          # 附带规范正文
wb domains
wb stats
```

### 知识推送

```bash
# 单个文件
wb push ./note.md --project 某客户 --tags "UDC,前端"

# 整个目录，递归收集 .md
wb push ./notes --path-tag "沉淀/某项目"

# JSON 批量（数组，每项含 title/content/path/tags）
wb push ./batch.json -y
```

会自动去重：内容没变时返回 `unchanged`，不会产生重复条目。

### 语雀同步（管理员）

```bash
wb sync               # 增量，只抓新增和更新的
wb sync --force       # 全量重抓
wb sync --limit 10    # 调试用，只抓 10 篇
```

首次全量约 1-3 分钟（231 篇），之后增量通常只有个位数。

### Key 管理（管理员）

```bash
wb key create local-agent --role writer       # 本地 agent 自动推送用
wb key create analyst --role reader           # 只读
wb key list
wb key revoke wr_abc123
```

key 只在创建时显示一次。

### 服务

```bash
wb health
wb serve --port 8770          # 启动 HTTP 服务
wb mcp                        # 启动 MCP stdio 服务
wb mcp --local                # 本地模式，不连远端
```

## 角色权限

| 角色 | search/read/rules | contribute | key 管理 / 同步 |
|---|---|---|---|
| `reader` | ✓ | ✗ | ✗ |
| `writer` | ✓ | ✓ | ✗ |
| `admin` | ✓ | ✓ | ✓ |

本地 agent 自动沉淀经验用 `writer`。人工只读查询用 `reader`。

## 配额

每个 key 有每分钟请求数和每日调用上限，超限返回 429 并在响应里给 `retry_after`。

管理端查用量：

```bash
wb --json stats
```

## 知识域与标签

常用 `domain` 取值：
`开发规范` / `扩展能力` / `集成平台` / `开发文档` / `UDC平台` / `BPM平台` / `业务组件` / `移动端开发` / `门户平台` / `数据迁移` / `V5V8融合` / `真实案例库` / `线上问题总结`

常用 `tag` 取值：
`SPI扩展` / `UDC` / `BPM` / `组织同步` / `待办同步` / `单点登录` / `MQ` / `Nacos` / `前端` / `移动端` / `签章` / `数据库` / `开放API` / `编码规范` / `安全` / `国际化`
