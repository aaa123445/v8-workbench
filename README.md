# V8 客开工作台

致远 V8 客开的知识检索、开发规范编排与经验沉淀服务。给本地 AI Agent（Claude Code / Codex / 自研 agent）提供"外部大脑"。

**它不负责编译部署。** 编译、打包、发布仍然走 V8 自身的 DevOps 能力。工作台只解决三件事：查得准、规范不漏、经验不丢。

## 解决什么问题

| 问题 | 后果 | 工作台的做法 |
|---|---|---|
| V8 平台 API 记不准 | 编译过、运行时不生效 | 强制先查文档，检索命中带出处 |
| 31 篇开发规范没人读完 | 提交后返工 | 按任务类型编排成自查清单 |
| 踩过的坑重复踩 | 同一个问题在新项目重演 | Agent 完成后主动沉淀，可检索 |

## 架构

```
本地 Mac / 开发机                          云服务器
┌────────────────────────────┐          ┌──────────────────────────┐
│ Claude Code / Codex / dsh  │          │  V8 客开工作台            │
│                            │  MCP     │  ├ HTTP API  (FastAPI)   │
│  ├ v8_search  ─────────────┼─────────▶│  ├ 检索引擎 (倒排+BM25)   │
│  ├ v8_read                 │  或 CLI  │  ├ 规范编排 (8 类任务)    │
│  ├ v8_rules                │          │  ├ 知识入库 (三来源)      │
│  └ v8_contribute ──────────┼─────────▶│  └ 语雀同步 (增量)        │
│                            │          │                          │
│ git clone 客开扩展仓库      │          │  SQLite + 内存索引        │
│ 写代码 → git push          │          │                          │
└──────────┬─────────────────┘          └──────────────────────────┘
           │
           ▼
    V8 DevOps 编译部署
```

## 三种形态的分工

这是这套东西最容易做错的地方，先把边界说清：

| 形态 | 提供什么 | 不提供什么 |
|---|---|---|
| **MCP** | 让 agent 自主决定何时调用的工具 | 不告诉 agent 什么时候该调 |
| **CLI** | 批量操作、脚本化、运维管理 | 不适合对话式交互 |
| **Skill** | 工作流程与判断准则 | 不含任何服务端逻辑或知识内容 |

关键判断：**只接 MCP 不装 Skill，agent 大概率放着工具不用**。MCP 解决"能查"，Skill 解决"该查什么、查到后怎么落地"。两样都要。

## 快速开始

### 服务器端

```bash
cd deploy
cp .env.example .env
# 生成一个管理员 key 填进 .env
python3 -c "import secrets;print('wb_ad_'+secrets.token_urlsafe(24))"

docker compose up -d
curl http://127.0.0.1:8770/health
```

首次启动是空的。导入现有语料（推荐，231 篇，离线可用）：

```bash
python3 ingest/load_corpus.py --skill-dir /path/to/seeyon-v8-kk
```

或者直接从语雀拉：

```bash
wb --url http://127.0.0.1:8770 --key <admin-key> sync
```

### 客户端

```bash
pip install -e /path/to/v8-workbench

export V8WB_URL=https://workbench.example.com
export V8WB_KEY=wb_rd_xxxxx
wb health
wb rules spi
```

**Claude Code 接 MCP**：

```bash
claude mcp add v8-workbench \
  --env V8WB_URL=https://workbench.example.com \
  --env V8WB_KEY=wb_rd_xxxxx \
  -- wb mcp
```

**Codex 接 MCP**（`~/.codex/config.toml`）：

```toml
[mcp_servers.v8-workbench]
command = "wb"
args = ["mcp"]
env = { V8WB_URL = "https://workbench.example.com", V8WB_KEY = "wb_rd_xxxxx" }
```

**装 Skill**：把 `skill/v8-workbench/` 拷到 agent 的 skill 目录。Claude Code 是 `~/.claude/skills/`。

## 工具一览

### MCP

| 工具 | 用途 |
|---|---|
| `v8_search` | 检索知识库 |
| `v8_read` | 读文档全文（支持分段） |
| `v8_rules` | 按任务类型取规范清单 + 自查项 |
| `v8_domains` | 列出知识域 |
| `v8_contribute` | 沉淀经验 |
| `v8_stats` | 知识库统计 |

### CLI

```bash
wb search "组织同步 中间表" -d 集成平台
wb read yuque:224228683
wb rules frontend --docs
wb domains
wb push ./notes --project 某客户 --tags "UDC,前端"
wb sync [--force] [--limit N]
wb key create local-agent --role writer
wb key list
wb key revoke wr_abc123
wb health
wb serve | wb mcp
```

加 `--json` 输出结构化结果，便于自研 agent 解析。

## 知识从哪来

三个来源，汇入同一个知识库：

| 来源 | 触发方式 | 角色 |
|---|---|---|
| **语雀同步** | 定时（默认每天）或 `wb sync` | admin |
| **本地 agent 沉淀** | agent 调 `v8_contribute` 或 `wb push` | writer |
| **管理员上传** | `wb push` / HTTP API | admin |

去重按内容 checksum，重复推送返回 `unchanged`，不会产生垃圾条目。

### 本地 agent 自动推送

给 agent 一个 `writer` key，在它的 skill 或配置里约定"任务完成后若踩到新坑就调 `v8_contribute`"。Skill 里已经写了判断标准：半年后别人搜到能不能直接用。

也可以用批处理方式，把一天的经验攒成 markdown 文件再推：

```bash
wb push ~/.v8wb/pending/ --project 某客户 -y
```

## 检索怎么工作的

三段式，不是纯向量：

1. **结构化路由** — 语雀的目录树（`开发规范 > 编码规范 > 命名风格`）是很强的先验
2. **BM25 关键词** — 中文用 bigram 分词，英文缩写整体保留（SPI/UDC/BPM）
3. **子串兜底** — 倒排零命中时扫正文，保证"怎么问都有结果"

为什么不用向量：231 篇、2.1MB 的语料，纯 BM25 + 路径先验的召回已经够用，加 embedding 只增加部署复杂度和冷启动延迟。等语料上到十万级再考虑。

排序里除了 BM25 还有三项独立加分：查询词覆盖率、标题承载率、路径承载率。这几项解决"搜『命名规范』时『UDC接入规范』排到『命名风格』前面"这类问题。

## 权限

| 角色 | 检索 | 沉淀 | 管理 |
|---|---|---|---|
| `reader` | ✓ | ✗ | ✗ |
| `writer` | ✓ | ✓ | ✗ |
| `admin` | ✓ | ✓ | ✓ |

每个 key 有每分钟请求数和每日调用上限，超限返回 429。

```bash
wb key create local-agent --role writer --rpm 60 --daily 5000
```

## 目录结构

```
v8-workbench/
├── server/
│   ├── config.py           环境变量配置
│   ├── core/
│   │   ├── db.py           SQLite schema 与事务
│   │   ├── tokenizer.py    中英混合分词
│   │   ├── index.py        倒排索引 + 混合检索
│   │   ├── docs.py         知识条目仓储、元数据推断
│   │   ├── rules.py        8 类任务规范编排
│   │   ├── auth.py         API Key 与配额
│   │   ├── yuque.py        语雀抓取与增量同步
│   │   ├── service.py      业务服务层（三入口共用）
│   │   └── container.py    依赖装配
│   └── api/
│       ├── http_app.py     FastAPI
│       ├── mcp_server.py   MCP stdio
│       └── scheduler.py    定时同步
├── cli/wb.py               CLI
├── skill/v8-workbench/     Agent skill
├── ingest/load_corpus.py   导入现有语雀语料
├── deploy/                 Docker / Nginx
└── tests/
```

## 开发

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python fastapi "uvicorn[standard]" pydantic httpx pyyaml python-multipart "mcp>=1.2" pytest

.venv/bin/python -m pytest tests/ -v
.venv/bin/python -m cli.wb serve --port 8770
```

## 已知边界

- **不碰 V8 环境**。不连数据库、不调 V8 接口、不做部署。工作台对 V8 一无所知，只有文档。
- **不做代码检索**。目前只检索文档和沉淀的经验，不索引客开源码仓库。这是刻意留的口子——代码检索需要先解决权限隔离和增量同步，价值高但成本也高，等文档层跑顺了再上。
- **单机 SQLite**。写入串行化，适合团队规模。多人高并发写入需要换 PostgreSQL。
- **不替代编译期校验**。自查清单是给 agent 和人的提示，不是 linter。真正的规范检查交给 V8 DevOps。

## 版本

0.1.0 — 知识检索 + 规范编排 + 经验沉淀 + 语雀同步。
