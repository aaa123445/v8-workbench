# TeamKB 团队知识共享平台

按分类共享团队知识，让本地 Agent 能检索文档、遵循团队规范，并沉淀经过验证的解决方案。项目由 V8 Workbench 演进而来，不局限于特定产品或平台。

- **知识工作台**：分类目录、全文检索、文档阅读、团队规范、版本历史与回滚。
- **协作与审核**：草稿、我的贡献、管理员审核、更新建议与版本冲突检查。
- **账号与凭据**：注册后审批入网、个人 API Key、角色权限、调用配额及个人调用日志。
- **Agent 接入**：一键生成 MCP / Skill / CLI 安装提示词，支持创建专用个人 Key、本机安装与连接验证。
- **经验沉淀**：按项目启用、结构化验证材料、默认审核；网络失败保存在本地队列并限次退避重试。
- **现有知识源**：语雀增量同步、V5 文档导入，V8 / V5 分类隔离；可增加其他团队知识分类。

## 访问入口

- [官网](https://www.ljc.monster/)
- [团队知识库](https://www.ljc.monster/#/library)
- [一键接入本地 Agent](https://www.ljc.monster/#/connect)
- [使用说明](docs/usage.md)：账号审批、个人 Key、MCP / Skill / CLI、任务完成 Hook 与审核。

在「一键接入」选择接入方式，复制提示词发给本地 Agent。默认推荐 MCP + Skill，也可只安装 CLI。可以在本机填写 Key，或明确选择随提示词复制个人 Key；不要将含 Key 的提示词提交到仓库或共享聊天。安装与连接状态以本地 Agent 实际验证结果为准。

## 架构

Vue 3 + Vue Router + Vite 提供前端；FastAPI 提供同源 HTTP API 与静态文件；SQLite 保存知识、账号、版本和审计。服务使用内存倒排索引、BM25 与全文兜底检索。CLI 与本地 stdio MCP 代理共用 HTTP API。

```text
本地 Agent ── MCP / CLI ── HTTPS API ── 知识服务 ── SQLite
    │                                      │
    └── team-knowledge Skill               └── 分类 / 规范 / 版本 / 审核
浏览器 ── Vue 工作台 ────── HTTPS API
```

MCP 通过本机 `wb mcp` 连接线上 API；网站没有远程 `/mcp` HTTP 端点。Skill 提供工作流程，本身不携带知识库，也不保证任务完成事件一定触发。

## 首次部署：Linux / systemd

需要 Python 3.11+、Git、Node.js 20.19+ 或 22.12+，以及 systemd。为兼容已有部署，服务器安装目录和服务名继续使用 `/opt/v8-workbench` 与 `v8wb`。

```bash
sudo git clone https://github.com/aaa123445/teamkb.git /opt/v8-workbench
# 确保 80 端口空闲：检查实际占用服务并按需停止。
sudo bash /opt/v8-workbench/deploy/install.sh
```

首次安装会创建服务账号、构建客户端与前端、监听 80 端口，并尝试同步已配置语雀知识库。请妥善保存脚本最后输出的初始管理员 Key，随后注册并审批个人管理员账号。公网访问应配置 HTTPS。

已有站点更新时先备份 SQLite，再执行：

```bash
cd /opt/v8-workbench
git pull --ff-only
sudo bash deploy/update.sh
```

更新脚本构建下载文件与前端、重启 `v8wb` 并检查健康状态，保留现有数据库、Key 和 TLS 配置。不要重跑首次安装脚本更新已有服务。

容器与反向代理配置见 [部署说明](docs/deployment.md) 和 `deploy/`。容器构建前需生成本站客户端/Skill 下载文件：`bash deploy/build-client.sh`；其输出不提交 Git。

## 本地开发与验证

```bash
git clone https://github.com/aaa123445/teamkb.git
cd teamkb
python3 -m venv .venv
.venv/bin/python -m pip install -e . pytest
# 可选：构建客户端下载文件，供一键接入页使用
bash deploy/build-client.sh
bash deploy/build-web.sh
V8WB_REQUIRE_AUTH=false .venv/bin/python -m cli.wb serve --host 127.0.0.1 --port 8770
```

关闭鉴权只用于本机开发。运行时数据默认在 `data/`，生产部署通过 `V8WB_DATA_DIR` 设置目录，不要提交数据库、配置密钥或导入的私有知识。

```bash
.venv/bin/python -m pytest -q
# 浏览器测试用拦截的接口数据；指定已启动的测试站点
cd web
npx playwright install chromium
E2E_BASE_URL=http://127.0.0.1:8770 npm run test:e2e
```

前端模块、开发代理和构建说明见 [web/README.md](web/README.md)。前端开发服务器默认代理本机 80 端口，可在 `web/vite.config.js` 调整。

## 常用工具

| 任务 | MCP | CLI |
| --- | --- | --- |
| 分类与规范 | `kb_categories` / `kb_rules` | `wb categories` / `wb standards` |
| 检索与阅读 | `kb_search` / `kb_read` | `wb search` / `wb read` |
| 提交方案 | `kb_propose` | `wb propose` |
| 查看贡献 | `kb_contributions` | `wb contributions` |
| 项目经验候选 | 通过 Skill 整理 | `wb agent init` / `wb agent complete` |
| 本地失败队列 | — | `wb queue list` / `wb queue retry` |

检索与阅读使用 reader 权限；提交经验需要 writer；审批、回滚和全局管理需要 admin。管理员可为指定 Key 授权自动发布，默认关闭，普通候选贡献仍进入审核。个人 Key 权限不能超过账号权限。

## 知识导入

语雀支持定时或管理员增量同步。已有 V8 语料可通过 `ingest/load_corpus.py` 导入；V5 Skill 仓库语料通过 `ingest/import_v5.py` 导入。抓取错误提示不会作为正文发布，CMP 页面修复流程见 [V5 导入说明](docs/v5-import.md)。源文档与生产修复快照不从 Git 仓库分发。

## 目录

```text
server/core/             账号、权限、知识、索引、版本与审核
server/api/              HTTP / MCP / 调用日志 / 同步调度
cli/                     CLI、项目候选提交与失败队列
web/src/                 Vue 工作台、官网与一键接入
skill/team-knowledge/    Agent 工作流、候选模板与任务完成脚本
skill/v8-workbench/      兼容原 V8 工作流
ingest/                  知识导入与 CMP 内容抓取
deploy/                  安装、升级、客户端与前端构建、容器
docs/                   使用与部署文档
tests/                   后端测试
web/tests/               桌面与手机浏览器测试
```

## 兼容性与边界

仓库改名为 `teamkb`；`wb` 命令、Python 分发名称 `v8-workbench`、既有下载文件名、`v8wb` 服务名、环境变量 `V8WB_*`、原文 ID 和旧 `v8_*` MCP 工具保持兼容。客户端也支持 `TEAMKB_URL` / `TEAMKB_KEY`。

平台保存和检索文档，不会执行知识内容中的代码，也不替代本地测试或编译检查。当前采用单机 SQLite；大规模并发写入需进一步扩展存储。经验提交前应在本地删除密钥、客户敏感信息和无关代码。

前端参考 MIT 许可的 Vue 官网及管理模板，保留 [来源与版权说明](web/THIRD_PARTY_NOTICES.md) 和 `web/public/licenses/` 许可文件。
