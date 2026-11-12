# 真实场景的完整调用序列

每个例子都标了"不这么做会怎样"，因为流程的价值在于知道省略哪一步会出事。

---

## 场景 1：客户要求「把 OA 系统的待办推到 V8」

### 错误做法

直接搜"待办"，拿到标题就写代码。结果写了一堆开放 API 调用，方向反了 —— 客户要的是三方推到 V8，写成了 V8 推三方。

### 正确序列

```bash
wb rules "三方待办推到V8"
```

返回 `integration` 画像，第一条自查就是"明确数据流向"。这一问会逼出关键信息：客户是哪个三方系统、用的什么接口。

```bash
wb search "三方到V8 待办同步"
wb search "批处理三方待办事项"
```

读到两篇：
- `集成平台 > 数据流向 > 三方到V8 > 待办同步` — 整体机制、状态映射
- `扩展能力 > 后端扩展 > SPI扩展 > 批处理三方待办事项` — 批量写入的实现方式

```bash
wb read yuque:xxxxx    # 先读待办同步，确认状态机
wb read yuque:xxxxx    # 再读批处理，确认批量接口
```

### 关键产物

回答里必须有：
- 数据流向明确写出来（三方 → V8）
- 待办状态映射表（三方的"已完成"对应 V8 的哪个状态）
- 标识映射（三方的任务 id 用哪个字段对应 V8 的事项 id）
- 幂等策略（重复推送怎么办）
- **待确认**：三方的回调是否可靠、是否有历史数据需要补推

最后一条最容易被漏。客户不会主动说"我们还有三年历史待办"，上线后发现列表是空的。

---

## 场景 2：写一个 SPI 扩展挂到登录流程

### 错误做法

凭记忆写 `implements UserLoginService`。编译过了，部署后不生效 —— 接口全名或方法签名在这个版本变了。

### 正确序列

```bash
wb rules spi
```

拿到必读规范：工程结构、接口规范、命名风格等，以及关键提醒"扩展点接口全名和签名必须与该 V8 版本一致"。

```bash
wb search "SPI扩展 登录"
wb read --title "登录扩展"
```

文档里会有准确的接口全名和示例实现。**这一步不能省** —— 接口名差一个字符就是不生效。

```bash
wb read --title "工程结构"
```

确认扩展实现类该放哪个包路径。放错包路径，Spring 扫不到，同样不生效。

### 关键产物

- 准确的 SPI 接口全名 + 方法签名（来自文档，不是记忆）
- 实现类的包路径（来自工程结构规范）
- 是否需要在客开管理后台注册（有些 SPI 需要显式注册）

---

## 场景 3：UDC 自定义页面上线后白屏

### 错误做法

改代码猜。前端白屏原因太多，猜的成本极高。

### 正确序列

```bash
wb search "UDC 自定义页面"
wb read --title "UDC接入规范"
wb read --title "自定义页面/组件 常见场景示例"
```

"常见场景示例"这篇有 5000 字，是场景最集中的一篇，白屏这类问题大概率有对应条目。

```bash
wb search "@seeyon/global"
wb read --title "@seeyon/global 使用指南"
```

白屏常见根因是平台 API 取值方式不对（直接 import 内部模块而不是走 global）。

### 修完之后的动作

问题解决后沉淀回去：

```bash
wb push ./udc-blank-screen.md --tags "UDC,前端"
```

标题要包含以后会搜的关键词：「UDC 自定义页面白屏 平台上下文未注入」。

---

## 场景 4：给客户的客开工程做代码自查

### 正确序列

```bash
wb rules spi --docs
```

`--docs` 会带出规范正文。这时是**一次性比对多处代码**，全展开反而划算。

逐条对照自查清单：
- 扩展类是否在正确包路径
- 外部调用是否有超时
- 空值语义是否明确
- 是否有单元测试

```bash
wb read --title "单元测试"
```

确认平台的单测约定（用哪个测试基类、怎么 mock 平台服务）。

### 注意

`--docs` 会返回几万字。只在**确实要逐条比对**时用。写新功能时用默认模式（只给清单）就够了。

---

## 场景 5：语雀知识库更新了，工作台要同步

```bash
wb sync
```

增量模式，只抓 `content_updated_at` 变化的。通常只有个位数。

```bash
wb sync --force
```

全量重抓，用于怀疑本地数据不一致时。231 篇约 1-3 分钟。

```bash
wb stats
```

确认同步后的文档数和知识域分布合理。

如果 `failed` 不为 0，看错误详情。语雀偶发 403/404 的文档是已知情况（公开 API 拿不到），不影响整体。

---

## 场景 6：团队新人的开发环境

```bash
# 1. 装 CLI
pip install -e /path/to/v8-workbench

# 2. 配置
export V8WB_URL=https://workbench.example.com
export V8WB_KEY=wb_rd_xxxxx

# 3. 验证
wb health
wb rules spi
```

Claude Code 里接 MCP：

```bash
claude mcp add v8-workbench \
  --env V8WB_URL=https://workbench.example.com \
  --env V8WB_KEY=wb_rd_xxxxx \
  -- wb mcp
```

Codex 用 `~/.codex/config.toml`：

```toml
[mcp_servers.v8-workbench]
command = "wb"
args = ["mcp"]
env = { V8WB_URL = "https://workbench.example.com", V8WB_KEY = "wb_rd_xxxxx" }
```

---

## 通用判断原则

**什么时候必须 read 全文**：

- 要写涉及平台 API 的代码 → API 名和签名必须来自文档
- 报错排查 → 需要看参数含义和边界条件
- 集成类需求 → 需要看状态机和字段映射

**什么时候 search 一次就够**：

- 确认某个能力平台是否提供（有就是有，没有再换词）
- 找有没有相关案例

**什么时候可以跳过**：

- 纯业务逻辑代码（不涉及平台 API）
- 你已经在这个会话里读过对应文档

**永远不要跳过**：`wb rules` 第一步。它的价值不是给知识，是防止漏项 —— 人会忘掉安全规约和单元测试，清单不会。
