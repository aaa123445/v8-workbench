# TeamKB 团队知识共享平台使用说明

TeamKB 统一提供分类知识管理、团队规范、贡献审核和 Agent 经验沉淀。原有致远 V8 内容保留在「技术平台 / 致远 V8」分类，原文 ID 和旧工具名称保持兼容。网页面向日常操作；CLI 面向终端和脚本；MCP 让 Agent 调用工具；Skill 定义查规范、读文档、写代码和沉淀经验的工作流程。MCP 与 Skill 可以配合使用，CLI 也可以单独使用。

本文命令以 macOS / Linux 的 Bash 或 Zsh 为例。服务地址示例为 `https://www.ljc.monster`；自行部署时换成你的实际域名。所有 `YOUR_PERSONAL_KEY` 均为占位符，不是可用凭据。

## 一键接入本地 Agent

在工作台左侧选择「一键接入」，推荐使用「MCP + Skill」，也可仅安装 MCP、Skill 或 CLI。页面会根据当前站点和客户端 SHA-256 校验清单生成安装提示词，复制后发送给你本机正在使用的 Agent，由它检查系统、安装独立 Python 环境、合并已有配置并验证连接。

可以留空 Key，在本机由 Agent 引导填写；也可粘贴已有个人 Key 并勾选「复制时包含个人 Key」。已入网账号可以直接创建 reader / writer 接入专用 Key，创建后用于本次提示词。个人中心刚创建的 Key 也可通过「用此 Key 生成安装提示词」带入。完整 Key 不放入链接或页面持久存储，离开接入页后清除本次填写内容；复制的提示词包含 Key 时，请只交给你信任的本地 Agent，不要发到共享聊天或提交到仓库。已创建的 Key 可在个人中心吊销。

默认只安装知识访问能力。「在当前开发项目启用经验候选提交」是可选项，需要 writer 权限；默认仍需管理员审核。接入页生成提示词不会自行修改本机或提交知识，实际安装由本地 Agent 完成。以其返回的鉴权、MCP 工具调用和 Skill 加载结果为准；需要重启 Agent 会话时按提示操作。

## 平台使用：分类、审核与版本

- 「团队知识库」按分类树浏览，点击标签可筛选；「知识检索」支持分类（包括子分类）内的全文检索。
- writer / admin 在「经验沉淀」保存草稿或提交审核。「我的贡献」可查看审核进度和意见，草稿与待审核内容不会出现在共享检索中。
- 管理员在「贡献审核」检查方案正文、验证材料、相似知识和适用限制，可发布、退回修改或拒绝。人工贡献不要求填写 Agent 的结构字段，由审核者判断质量。
- 修正已有知识时，从文档页「建议更新」发起。它关联目标文档的当前版本，审核时若版本已变化会拒绝覆盖，需退回后重新核对并提交。
- 文档页「版本历史」可以查看历史快照。管理员恢复历史版本时会新建一个版本，保留原有历史。
- 「分类管理」可维护分类层级；「团队规范」可编辑分类对应的规范、检查清单和参考文档，供网页与 `kb_rules` 共用。
- 语雀仍是已配置外部知识的同步来源；后续同步可能更新其正文，同时保留版本快照。需要独立维护的团队经验应创建新知识并引用原文。
- 个人调用日志会记录检索、阅读、提交、审核和回滚等调用的状态与结果，仍按账号隔离并执行保留期限。

## Agent 自动沉淀：项目开关与候选材料

先安装下文 CLI，在客户端设置 `TEAMKB_URL` 与 `TEAMKB_KEY`（或继续使用兼容的 `V8WB_URL` / `V8WB_KEY`）。新版客户端需要本次更新后的代码；已安装的旧客户端应更新本地源码。以下命令在开发项目中执行：

```bash
export TEAMKB_URL="https://www.ljc.monster"
export TEAMKB_KEY="YOUR_PERSONAL_KEY"
wb agent init --project /absolute/path/to/project
```

命令创建 `.teamkb/config.json`，内容为 `{"enabled": true, "candidate_file": ".teamkb/candidate.json"}`。只对该项目启用；停用时将 `enabled` 改为 `false`。建议把 `.teamkb/candidate.json`、`.teamkb/submitted.json` 加入项目 `.gitignore`，不要把 Key 写进项目配置。

把仓库的 `skill/team-knowledge/references/candidate.json` 复制为项目候选文件，再由 Agent 根据实际任务填写。模板故意将 `verified` 与 `reusable` 设为 false，不能直接提交。Agent 材料要求：问题至少 10 字符、解法至少 20 字符、真实验证说明至少 10 字符、限制至少 5 字符、正文至少 80 字符，并明确 `verified: true`、`reusable: true`。这些是完整性门槛，不代表系统已替你验证方案正确性。

```bash
# 人工触发一次任务完成处理：只读取候选文件，不扫描仓库或会话
wb agent complete --project /absolute/path/to/project
# 显式提交一个经过验证的方案
wb propose /absolute/path/to/candidate.json
# 材料尚未验证时，只保存草稿
wb propose /absolute/path/to/candidate.json --draft
wb contributions
wb contributions CONTRIBUTION_ID
```

默认结果是 `pending`（待审核），审核后才共享。同一候选重复执行会去重；修正已有文档请设置 `target_doc_id` 和 `base_version`（来自读取结果的 `knowledge_version`）。新 MCP 工具为 `kb_categories`、`kb_search`、`kb_read`、`kb_rules`、`kb_propose`、`kb_contributions`，传参及返回结构可在 API 文档中查看。旧 `v8_*` 工具保留；旧 `v8_contribute` / `wb push` 也进入人工审核，不直接发布。

MCP 在 `local` 离线模式下只操作本地库，候选不会发送给团队服务器，也不会自动发布。需要团队共享请使用默认 proxy 模式。

## 失败重试与任务完成 Hook

网络失败、HTTP 429 或 5xx 时，`wb propose` / `wb agent complete` 会将候选保存在 `~/.teamkb/queue`（目录 700、文件 600），不保存 Key。单次最多保存 100 条，按服务地址隔离。重试使用当前环境中的 Key，请保持原来的账号身份。

```bash
wb queue list
wb queue retry
# 修复凭据或材料错误后，手动重置 blocked / exhausted 项再重试
wb queue retry --reset
# 无效或过时材料：移除旧队列条目，修改候选文件后重新提交
wb queue remove QUEUE_ID
```

重试最多 5 次，指数退避，尊重数值 Retry-After；401/403 等不可重试错误会变为 `blocked`，达到次数上限变为 `exhausted`。`retry` 只处理已到重试时间的条目，调度由你的任务完成脚本或定时任务调用，本工具不会自行常驻。成功后删除队列条目；本地成功状态用于防止同一候选重复提交。长时间离线后请检查候选是否仍有效。

通用完成命令为 `wb agent complete --project PROJECT_ROOT`。任何支持任务完成事件的 Agent 都可在该事件中执行此命令，项目未开启或没有候选文件时会跳过。Skill 只是工作流程指导，不能保证每个 Agent 在每次退出时都运行；需要确定性触发时配置 Hook。

仓库提供 `skill/team-knowledge/scripts/completion_hook.py`：从标准输入读取带 `cwd` 的 JSON，只在这个目录明确启用时运行；不读 transcript、不执行候选中的命令，错误不会阻断主任务。必须用安装了客户端的虚拟环境 Python 运行。

Claude Code 项目 `.claude/settings.json` 的示例（合并到已有配置，不要覆盖其他 Hook）：

```json
{
  "hooks": {
    "Stop": [{"hooks": [{
      "type": "command",
      "command": "/absolute/path/to/v8-workbench/.venv/bin/python /absolute/path/to/v8-workbench/skill/team-knowledge/scripts/completion_hook.py",
      "timeout": 90
    }]}]
  }
}
```

Hook 用事件 `cwd` 找项目配置，子目录启动时需要在该目录启用，或改用固定项目根目录的完成命令。不要同时通过 MCP 和 Hook 提交同一方案。

管理员可以在「工作台管理」对指定 writer/admin Key 授权自动发布。仅限该 Key 提交的 Agent 材料满足全部完整性条件、没有相似已发布知识时才自动发布，并记录审核事件；普通人工提交和更新建议仍按审核流程处理。相似度仅为标题与内容指纹的启发式检查，不是语义查重。默认所有 Key 都关闭此权限，个人账号不能自行开启。

凭据模式检测只是一层辅助检查，不能识别所有敏感数据；Agent 应在本地先删除密码、Token、客户信息与无关代码。队列只存已经整理的候选，不应包含原始会话。

## 1. 开通账号与个人 Key

1. 在工作台右上角选择「登录 / 注册」，进入「注册入网」。填写姓名、用户名和至少 10 个字符的密码。
2. 注册后自动登录个人中心，账号状态为「待审批」。此时只能查看自己的状态、修改密码和阅读使用说明，不能查询知识库或创建 Key。
3. 联系管理员核实身份。管理员在「工作台管理 → 账号审批与管理」中选择角色，点击「批准入网」。注册不会自动获得管理员权限。
4. 在个人中心刷新状态，获批后即可直接使用网页，无需配置 API Key。
5. 在「个人中心 → 我的 API Key」输入名称、选择权限并创建。完整 Key 只显示一次，请立即保存。建议每台电脑或每个 Agent 单独使用一个 Key。

| 角色 | 检索与阅读 | 提交经验 | 审批与全局管理 |
| --- | --- | --- | --- |
| reader / 只读成员 | 支持 | 不支持 | 不支持 |
| writer / 读写成员 | 支持 | 支持 | 不支持 |
| admin / 管理员 | 支持 | 支持 | 支持 |

个人 Key 权限不能超过账号权限，每个账号最多启用 20 个 Key。账号被降级后，已有 Key 的有效权限也会随之降低。账号被拒绝或停用时，个人 Key 全部吊销；重新批准账号不会复活旧 Key，需要重新创建。

浏览器登录与客户端 Key 是两种凭据：密码用于登录网页，Key 用于 MCP、CLI 等客户端。不要把密码填进 `V8WB_KEY`。修改密码会使所有浏览器登录会话退出；如 Key 泄露，还需在个人中心单独吊销。

## 2. 安装 CLI 与公共环境

推荐直接安装与当前服务器一致的客户端（无需等待 GitHub 源码同步）：

```bash
python3 -m venv ~/.teamkb-venv
source ~/.teamkb-venv/bin/activate
python -m pip install "https://www.ljc.monster/static/downloads/v8_workbench-0.5.0-py3-none-any.whl"
wb --help
```

Skill 压缩包：[下载 team-knowledge 0.5.0](/static/downloads/team-knowledge-0.5.0.zip)。解压后把完整 `team-knowledge` 文件夹放到客户端的 Skill 目录；任务完成脚本和候选模板一并包含。校验信息：[下载文件 SHA-256 清单](/static/downloads/manifest.json)。

下面是从源码安装的方式，需确认克隆源码已包含 `kb_*` 工具和 `skill/team-knowledge`：

客户端需要 **Python 3.11+**、Git，以及能访问工作台的网络。客户端不需要安装 Node.js，也不需要启动 HTTP 服务或同步语雀。

在你的开发电脑执行：

```bash
mkdir -p "$HOME/tools"
cd "$HOME/tools"
git clone https://github.com/aaa123445/teamkb.git
cd teamkb
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
wb --help
```

后续再次打开终端时，先激活这个虚拟环境，或直接使用 `.venv/bin/wb` 的绝对路径。Windows PowerShell 中激活命令为 `.\.venv\Scripts\Activate.ps1`，可执行文件路径为 `.venv\Scripts\wb.exe`。

配置地址和个人 Key：

```bash
export V8WB_URL="https://www.ljc.monster"
# 下面的值换成个人中心创建的 Key。
export V8WB_KEY="YOUR_PERSONAL_KEY"
wb health
wb stats
```

PowerShell 设置环境变量：

```powershell
$env:V8WB_URL = "https://www.ljc.monster"
$env:V8WB_KEY = "YOUR_PERSONAL_KEY"
wb health
wb stats
```

`health` 免鉴权，只能验证服务连通；`stats` 成功返回文档数量，才表示 Key 验证通过。需要持久保存环境变量时，放到你自己管理的本地配置中，不要提交到 Git 或共享配置。轮换 Key 后要同步更新客户端并重启 Agent。

升级客户端：进入克隆目录，执行 `git pull --ff-only` 和 `python -m pip install -e .`。

## 3. MCP 安装与接入

本项目目前提供 **本地 stdio MCP 代理**：Agent 启动本机的 `wb mcp`，由它调用工作台 HTTPS API。不要把网站地址直接当作远程 MCP URL；本项目没有对外提供 `/mcp` HTTP 服务，也不使用 OAuth 登录。

先完成上一节 CLI 安装，并确认 `wb stats` 成功。以下路径必须换成你开发电脑上的绝对路径。

### Codex

在 `~/.codex/config.toml` 增加：

```toml
[mcp_servers.v8-workbench]
command = "/absolute/path/to/v8-workbench/.venv/bin/wb"
args = ["mcp"]
env_vars = ["V8WB_URL", "V8WB_KEY"]
startup_timeout_sec = 20
tool_timeout_sec = 60
```

先在终端导出 `V8WB_URL`、`V8WB_KEY`，再从该终端启动 Codex。`env_vars` 用于转发启动环境中的变量。桌面应用或 IDE 不一定继承终端环境，此时可在本机配置中用下列环境段显式配置，并妥善保护该文件：

```toml
[mcp_servers.v8-workbench.env]
V8WB_URL = "https://www.ljc.monster"
V8WB_KEY = "YOUR_PERSONAL_KEY"
```

检查配置：

```bash
codex mcp list
```

重新开启会话，在 Codex 的 `/mcp` 中检查 `v8-workbench` 是否已连接。连接后请求：“调用 v8_stats 验证工作台，然后检索组织同步文档。”

### Claude Code

激活客户端虚拟环境、设置环境变量后，在克隆目录执行：

```bash
claude mcp add --transport stdio --scope user \
  --env V8WB_URL="$V8WB_URL" \
  --env V8WB_KEY="$V8WB_KEY" \
  v8-workbench -- "$PWD/.venv/bin/wb" mcp
claude mcp list
```

该命令将 Key 写进本机用户配置，请勿分享该配置。重新打开 Claude Code，通过 `/mcp` 查看连接状态。若弹出工具授权，按实际需要批准。

### 其他支持 stdio 的 MCP 客户端

下面是常见的 `mcpServers` 配置格式。不同客户端配置文件位置可能不同，以其官方说明为准。

```json
{
  "mcpServers": {
    "v8-workbench": {
      "command": "/absolute/path/to/v8-workbench/.venv/bin/wb",
      "args": ["mcp"],
      "env": {
        "V8WB_URL": "https://www.ljc.monster",
        "V8WB_KEY": "YOUR_PERSONAL_KEY"
      }
    }
  }
}
```

### 可用工具与验证任务

| MCP 工具 | 用途 |
| --- | --- |
| `v8_stats` | 检查知识库规模与连接 |
| `v8_domains` | 列出知识领域 |
| `v8_rules` | 按开发任务获取规范与自查清单 |
| `v8_search` | 用平台术语检索文档 |
| `v8_read` | 读取正文；长文按 next_offset 续读 |
| `v8_contribute` | 兼容旧客户端：提交待审核经验，需要 writer 或 admin Key |

验证提示词：“我要做 V8 组织同步扩展。请先用 v8_rules 获取 integration 规范，再检索组织同步，打开最相关的文档，列出适用版本和实现依据。”

`wb mcp` 启动后安静等待输入是正常现象，它不是交互式终端程序。只有需要本机离线知识库时才使用 `wb mcp --local`；该模式不连接线上，也不会自动下载线上文档。

## 4. Skill 安装与使用

Skill 是本仓库的 `skill/team-knowledge/` 目录，包含 `SKILL.md`、`references/` 和 `scripts/`。请复制整个目录，不能只复制 `SKILL.md`。Skill 约定工作流程，本身不携带知识库；仍然需要已经可用的 MCP 或 `wb` CLI。

先进入上文克隆的 `v8-workbench` 仓库目录，再执行相应命令。

### Codex：用户级安装

```bash
mkdir -p "$HOME/.agents/skills"
cp -R skill/team-knowledge "$HOME/.agents/skills/"
```

也可在你实际开发的项目根目录创建 `.agents/skills/`，把同一目录放进去，作为项目级 Skill。确认目标文件是 `.agents/skills/team-knowledge/SKILL.md`，不要多嵌套一层同名目录。

重新开启 Agent 会话，确认能发现 `team-knowledge`。示例：“请使用 team-knowledge skill，帮我规划一个 V8 SPI 扩展，先查规范与文档再给方案。”

### Claude Code：用户级安装

```bash
mkdir -p "$HOME/.claude/skills"
cp -R skill/team-knowledge "$HOME/.claude/skills/"
```

项目级安装则放到实际开发项目的 `.claude/skills/team-knowledge/`。重新开启会话后，可通过 `/team-knowledge` 或明确要求使用这个 Skill 启动工作流程。

### 推荐使用顺序

1. 识别任务所属分类，用 `kb_categories` 与 `kb_rules` 或 `wb categories` 与 `wb standards` 获取分类和规范。
2. 用 `kb_search` 或 `wb search` 检索，再用 `kb_read` 或 `wb read` 读取相关原文。
3. 基于文档与项目版本实施代码，完成提交前自查。
4. 如果发现可复用的新经验，用 `kb_propose` 或 `wb propose` 提交审核。提交前移除客户敏感数据和密钥。

升级 Skill：从更新后的仓库重新同步整个 `skill/team-knowledge/` 目录；保留你自己的其他 Skill 不变。

## 5. CLI 常用命令

以下命令依赖前面已设置的 `V8WB_URL` 与 `V8WB_KEY`。全局参数如 `--json`、`--timeout` 要放在子命令之前。

```bash
# 连通性和凭据验证
wb health
wb stats

# 查领域与规范
wb domains
wb rules spi
wb rules integration --docs

# 检索，限制返回数量或知识领域
wb search "组织同步 中间表" -n 5
wb search "SPI 扩展" -d "扩展能力"
wb --json search "UDC 页面"

# 用实际搜索结果中的文档 id 读取
wb read "yuque:实际文档ID"
wb read "yuque:实际文档ID" --offset 6000 --max-chars 6000
wb read --title "实际文档标题"

# 沉淀单篇或整个目录，需要 writer/admin
wb push ./notes/example.md --project "脱敏项目名" --tags "UDC,前端"
wb push ./notes --project "脱敏项目名" -y
```

人工贡献正文至少 20 个字符，提交后由管理员审核。`wb push` 默认会展示待上传条目并要求确认，`-y` 用于已审核的脚本场景。重复内容会去重；请先在本地检查文件内容，不要误传整个项目。

个人 Key 的创建与吊销在网页「个人中心」完成。下面的 CLI 管理命令属于全局管理员功能，普通账号的 Key 不能使用：

```bash
wb key list
wb key create local-agent --role writer --rpm 60 --daily 5000
wb key revoke --prefix wr_实际前缀
wb --timeout 600 sync
```

## 6. 管理员操作与迁移

既有部署的管理员 Key 仍有效，可在「登录 / 注册 → 使用已有 API Key」中连接。随后在「工作台管理 → 账号审批与管理」审批注册申请。为本人创建管理员账号时，先正常注册并退出新账号，再在登录页使用原管理员 Key，将该账号批准为 admin；不会把首个注册者自动设为管理员。

审批时可选择 reader、writer 或 admin，填写可选的审批说明。不要给仅需检索或提交经验的成员分配 admin。被拒绝或停用的账号可以由管理员重新批准。

「我的 API Key」只显示本人 Key；「工作台管理 → API Key 管理」是管理员的全局列表，包含归属账号和旧版系统 Key。新管理员账号通过全局页面创建的 Key 也会归属自己；原有无归属 Key 保持兼容，不会自动转给任意注册者。

账号密码使用带随机盐的 PBKDF2 哈希保存；浏览器会话通过 HttpOnly Cookie 保存。登录会话有效期 7 天；退出或改密码会撤销会话。HTTPS 访问时 Cookie 设置 Secure。个人 Key 仅保存哈希。

管理员不能停用或降级当前管理员账号，也不能移除最后一个已批准的管理员账号。保留原部署管理员 Key，直到你确认新管理员账号可正常登录、审批和管理。

部署升级前备份 SQLite 数据库。新增账号表、会话表、审批记录和 Key 归属字段由启动时自动迁移；升级时使用 `deploy/update.sh`，不要重跑首次安装脚本来更新现有站点。

## 7. 常见问题与排查

| 现象 | 排查方式 |
| --- | --- |
| 已注册但看不到知识或不能创建 Key | 登录个人中心查看审批状态；待审批、拒绝和停用状态均不可使用 |
| 无法创建 writer/admin Key | Key 角色不可高于账号角色；需要更高权限请联系管理员 |
| 401 / 凭据无效 | 网页重新登录；客户端检查 V8WB_KEY、Key 是否吊销、账号是否被停用 |
| 403 / 权限不足 | 检查账号审批状态以及 Key 角色；writer 才能提交经验，admin 才能审批或同步 |
| 429 | 达到调用额度或登录限流，按提示等待；不要让脚本无限重试 |
| MCP 找不到 wb | 使用虚拟环境内 wb 的绝对路径；Windows 指向 wb.exe |
| MCP 连上但没有查到内容 | 先调 v8_stats 验证连接，再用更短的平台术语检索 |
| Agent 看不到环境变量 | 从设置好环境变量的终端启动，或在本机客户端配置中设置 env；重启 Agent |
| Skill 未出现 | 确认目录下有 SKILL.md，整个目录已复制；检查安装位置与客户端支持，重新打开会话 |
| CLI health 成功但 stats 失败 | health 不检查凭据；检查个人 Key 和批准状态 |
| 长文未读完 | 根据 next_offset 继续读取，CLI 使用 --offset |
| 找不回完整 Key | 无法重新查看；吊销旧 Key 后创建新 Key，再更新各客户端 |
| 忘记账号密码 | 联系管理员核实身份；当前版本未实现邮件找回，不能靠 Key 直接查询或重置密码 |

先运行 `wb --help` 与 `wb stats`，再排查 MCP／Skill。工作台网站的网页 Cookie 不会自动传给 MCP 或 CLI，客户端始终需要个人 Key。

## 8. 配置参考

客户端配置参照以下官方文档，并与本仓库的 `cli/wb.py`、`server/api/mcp_server.py` 和 `skill/team-knowledge/` 实现核对。不同客户端版本的界面可能不同。

- [OpenAI 官方 MCP 配置说明](https://developers.openai.com/codex/mcp/)
- [OpenAI 官方 Skills 目录与使用说明](https://developers.openai.com/codex/skills/)
- [Claude Code MCP 配置说明](https://code.claude.com/docs/en/mcp)
- [Claude Code Skills 使用说明](https://code.claude.com/docs/en/skills)

## 9. 个人调用日志

从侧栏「我的调用日志」或「个人中心 → 我的调用日志」进入。账号登录时，可以查看自己的网页调用及全部个人 Key 的历史；通过 API Key 连接时，只能查看当前 Key 的调用，管理员 Key 也没有查询其他账号日志的特殊入口。

记录知识检索、文档读取、规范、领域、统计、最近更新、知识提交、批量提交、删除、语雀同步与索引重建。每条日志包含调用开始时间、操作、来源、Key 前缀与名称、HTTP 状态、成功/失败/部分成功、耗时、请求参数和返回结果。筛选支持关键词、类型、来源、Key、状态与日期，并支持分页。点击「查看」可切换请求和结果快照、复制当前内容。

登录、密码、Key 管理及日志查询接口不保存调用快照；查询日志不会递归记日志或占用调用额度。认证失败、无法确认归属的请求不会写入个人历史。账号必须已批准，才能查看账号日志。

- 日志从本次功能上线后开始记录。旧用量记录没有保存结果，不能补录。
- 默认保留最近 **30 天、每个账号最多 2,000 条**，未绑定账号的旧 Key 按当前 Key 限额保留。新调用写入时清理过期与超额记录；查询仅展示保留期内的记录。
- 请求快照最多 **16 KiB**，返回快照最多 **64 KiB**；较长内容会截断并标记。极大或无法解析的 JSON 正文不保存原文。读取长文时，只记录本次返回的分段。
- 密码、Token、Cookie、完整工作台 Key 等敏感字段会隐藏；详情显示的是脱敏快照。凭据请求头不采集。
- Key 吊销后，其历史仍归原账号所有，可以通过账号登录查看；被吊销的 Key 本身无法再查询日志。
- 网页、更新后的 MCP 和 CLI 客户端分别标记为 web、mcp、cli；旧客户端可能显示为 API。Skill 的调用按其实际使用的 MCP 或 CLI 记录，本地离线 `wb mcp --local` 不经过服务器，不产生线上个人日志。

管理员可通过环境变量 `V8WB_CALL_LOG_RETENTION_DAYS`（默认 30）和 `V8WB_CALL_LOG_MAX_ENTRIES`（默认 2000）调整保留策略。详细日志清理与调用配额统计分开，不会因历史被清理而重置当日额度。

任务完成事件格式参考 [Claude Code 官方 Hooks 文档](https://code.claude.com/docs/en/hooks)。
