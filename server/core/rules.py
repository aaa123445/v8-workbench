"""开发规范编排。

agent 的真实痛点不是"查不到规范"，而是"不知道该查哪几篇、什么时候查"。
所以这一层按【任务类型】把散落的规范文档编排成一份可执行清单，
每类任务给出：必读规范 → 相关扩展点 → 检查项 → 常见坑。

检查项（checklist）是给 agent 自查用的，不是给机器执行的 linter。
真正的 lint 交给 V8 DevOps 侧，这里只做提示。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TaskProfile:
    key: str
    name: str
    aliases: tuple[str, ...]
    # 需要阅读的规范文档标题（精确匹配语雀标题）
    must_read: tuple[str, ...] = ()
    # 该任务的扩展点/开发文档
    reference: tuple[str, ...] = ()
    # 自查清单
    checklist: tuple[str, ...] = ()
    # 常见坑
    pitfalls: tuple[str, ...] = ()
    # 相关标签，用于补充检索
    tags: tuple[str, ...] = ()


PROFILES: tuple[TaskProfile, ...] = (
    TaskProfile(
        key="spi",
        name="后端 SPI 扩展",
        aliases=("spi", "扩展点", "后端扩展", "接口扩展", "事件监听", "listener"),
        must_read=("工程结构", "接口规范", "Rest规范", "安全规约", "命名风格", "注释规约", "单元测试"),
        reference=("SPI扩展", "事件监听", "后端常用方法", "客开管理"),
        checklist=(
            "确认扩展点接口全名与实现的 SPI 版本，接口方法签名与当前 V8 版本一致",
            "扩展实现类放在客开工程约定的包路径下，不要放进 seeyon 平台包",
            "实现类标注 @Service/@Component 且确认能被 Spring 扫描到",
            "外部依赖（DB/MQ/HTTP）必须有超时和异常兜底，不能抛到平台线程",
            "返回值遵循平台约定，空值语义明确（null 与 空集合含义不同）",
            "补充单元测试，覆盖正常/异常/空值三条路径",
        ),
        pitfalls=(
            "扩展类重名或包名冲突导致平台加载失败",
            "在扩展点里做长耗时同步操作，拖垮平台线程池",
            "直接改平台核心代码而非走扩展点，升级后全部丢失",
        ),
        tags=("SPI扩展",),
    ),
    TaskProfile(
        key="udc",
        name="UDC 应用/组件开发",
        aliases=("udc", "自定义页面", "微流程", "自定义组件", "自定义栏目", "设计器组件"),
        must_read=("UDC接入规范", "编码规范", "客开自定义组件文档", "前端开发规范", "前端目录结构和编码规范"),
        reference=("UDC SDK 开发文档", "udcSdk的基本方法", "自定义页面", "自定义微流程", "自定义页面/组件 常见场景示例", "泛化调用"),
        checklist=(
            "确认使用 UDC SDK 的版本与 V8 版本匹配",
            "页面/组件注册信息（编码、名称、类型）在应用内唯一",
            "udcSdk 调用统一走封装层，不散落在业务代码里",
            "自定义微流程的入参出参结构与绑定位置一致",
            "前端组件遵循 module federation 与 @seeyon/global 约定",
        ),
        pitfalls=(
            "3.15 之前版本的扩展代码构建方式不同，勿混用",
            "自定义页面直接读平台内部 store，升级即断",
        ),
        tags=("UDC",),
    ),
    TaskProfile(
        key="bpm",
        name="BPM 流程扩展",
        aliases=("bpm", "流程", "流程按钮", "流程触发", "工作流", "审批"),
        must_read=("Rest规范", "接口规范", "安全规约", "命名风格"),
        reference=("BPM功能扩展", "BPM组件扩展", "流程按钮扩展行为", "流程触发方法", "BPM微流程绑定位置"),
        checklist=(
            "确认扩展的是流程按钮、流程触发还是微流程绑定，三者机制不同",
            "流程触发要区分节点前后的执行时机与事务边界",
            "流程处理中对单据的操作要避免与平台事务冲突",
            "驳回/撤销/终止等异常路径都要覆盖",
        ),
        pitfalls=(
            "在流程事件里做外部 HTTP 调用导致流程卡死",
            "假设流程节点编码固定，客户改流程后失效",
        ),
        tags=("BPM",),
    ),
    TaskProfile(
        key="frontend",
        name="前端扩展",
        aliases=("前端", "组件", "react", "vue", "jssdk", "页面扩展", "插槽", "门户元素"),
        must_read=(
            "前端开发规范", "前端目录结构和编码规范", "前端接口请求规范",
            "前端依赖管理", "应用状态规范", "模块联邦(MF)使用指南",
            "@seeyon/global 使用指南",
        ),
        reference=(
            "平台页面js/css/jssdk扩展", "扩展插槽", "自定义行为扩展",
            "自定义门户元素", "平台页面html", "udc自定义组件",
            "前端常用组件整理及api",
        ),
        checklist=(
            "平台 API 一律通过 @seeyon/global 获取，不直接 import 平台内部模块",
            "请求统一走平台请求封装，含 token 与租户头",
            "组件遵循模块联邦暴露约定，避免打包进主包",
            "样式隔离，不用全局选择器污染平台页面",
            "依赖版本与平台基线对齐，不引入冲突的大版本",
        ),
        pitfalls=(
            "直接操作平台 DOM 结构，平台升级后样式错乱",
            "把平台内部组件当公共组件引用，构建时模块联邦断链",
        ),
        tags=("前端",),
    ),
    TaskProfile(
        key="integration",
        name="集成平台（三方单点/组织/待办/消息同步）",
        aliases=("集成", "单点登录", "sso", "组织同步", "待办同步", "消息同步", "开放api", "三方"),
        must_read=("接口规范", "Rest规范", "安全规约", "MQ消息规范", "数据库规范"),
        reference=(
            "三方到V8 > 单点登录", "V8到三方 > 单点登录", "三方到V8 > 组织同步",
            "V8到三方 > 组织同步", "三方到V8 > 待办同步", "V8到三方 > 待办同步",
            "三方到V8 > 消息同步", "V8到三方 > 消息同步", "开放API", "接口注册",
        ),
        checklist=(
            "明确数据流向：V8→三方 / 三方→V8 / 双向",
            "确认标识映射（账号、组织编码、事项 id）的唯一键",
            "凭证管理走平台配置，禁止硬编码",
            "回调接口必须幂等，支持平台重推",
            "失败要有重试与死信，不能静默丢弃",
            "大数据量同步走批处理，不逐条调用",
        ),
        pitfalls=(
            "组织同步只看增量不做删除处理，导致离职人员残留",
            "待办状态不同步闭环，待办永远停留在待办列表",
            "单点票据未做时效校验，存在重放风险",
        ),
        tags=("单点登录", "组织同步", "待办同步", "开放API"),
    ),
    TaskProfile(
        key="data",
        name="数据库/数据迁移",
        aliases=("数据库", "sql", "建表", "迁移", "数据迁移", "表结构"),
        must_read=("数据库规范", "安全规约", "命名风格", "工程结构"),
        reference=(
            "V5CAP4数据迁移V8说明", "V5公文数据迁移V8说明", "V5文档中心数据迁移V8说明",
            "V5新闻公告数据迁移V8说明", "V5自由协同数据迁移V8说明",
            "数据源扩展", "Mybatis组件", "DynamicSQL组件",
        ),
        checklist=(
            "客开表统一前缀，避免与平台表冲突",
            "主键、索引、字符集遵循平台规范",
            "DDL 与 DML 分离，脚本可重复执行",
            "大表变更评估锁表时间，走低峰窗口",
            "迁移任务可断点续跑且幂等",
        ),
        pitfalls=(
            "直接查询平台内部表，跨版本字段变更即报错",
            "绕过平台数据权限直接 SQL 取数，越权",
        ),
        tags=("数据库",),
    ),
    TaskProfile(
        key="docs",
        name="客开交付文档撰写",
        aliases=("文档", "需求设计", "设计文档", "接口文档", "交付文档", "验收文档"),
        must_read=("接口规范", "Rest规范", "Swagger规范", "名词解释"),
        reference=("开放API", "接口注册"),
        checklist=(
            "需求文档：写明业务背景、范围边界、不在范围内的部分",
            "设计文档：扩展点选型理由 + 数据流 + 异常与回滚策略",
            "接口文档：字段级说明含类型、必填、取值约束、示例",
            "明确环境依赖与前置配置（白名单、注册中心、密钥）",
            "列出已知限制和后续待办",
        ),
        pitfalls=(
            "接口文档只写字段名不写取值范围，联调反复",
            "漏写权限与租户相关前提",
        ),
        tags=(),
    ),
    TaskProfile(
        key="general",
        name="通用客开",
        aliases=("通用", "其他"),
        must_read=("工程结构", "命名风格", "注释规约", "安全规约", "代码提交规范"),
        reference=("开发准备", "后端常用方法", "前端常用组件整理及api"),
        checklist=(
            "先确认需求落在扩展点范围内还是确实需要客开",
            "客开代码与平台代码物理隔离",
            "配置项外置，不写死在代码里",
        ),
        pitfalls=("把可配置的差异做成代码分支，客户一多就不可维护",),
        tags=(),
    ),
)

_BY_KEY = {p.key: p for p in PROFILES}


def resolve_profile(task: str) -> TaskProfile:
    """把 agent 传的任务描述/类型映射到最接近的 profile。

    先用精确 key，再用别名子串。都命中不了返回 general。
    """
    t = (task or "").strip().lower()
    if not t:
        return _BY_KEY["general"]
    if t in _BY_KEY:
        return _BY_KEY[t]
    best: tuple[int, TaskProfile] | None = None
    for p in PROFILES:
        score = 0
        if p.key in t or p.name in task:
            score += 10
        for a in p.aliases:
            if a.lower() in t:
                score += 3 + min(len(a), 4)
        if score and (best is None or score > best[0]):
            best = (score, p)
    return best[1] if best else _BY_KEY["general"]


def list_profiles() -> list[dict]:
    return [
        {
            "key": p.key,
            "name": p.name,
            "aliases": list(p.aliases),
            "must_read": list(p.must_read),
            "checklist_count": len(p.checklist),
        }
        for p in PROFILES
    ]


def render_brief(p: TaskProfile) -> str:
    """渲染成 agent 直接可读的 Markdown。"""
    lines = [f"# {p.name}（{p.key}）", ""]
    if p.must_read:
        lines.append("## 必读规范")
        lines += [f"- {x}" for x in p.must_read]
        lines.append("")
    if p.reference:
        lines.append("## 相关扩展点与样例")
        lines += [f"- {x}" for x in p.reference]
        lines.append("")
    if p.checklist:
        lines.append("## 提交前自查")
        lines += [f"- [ ] {x}" for x in p.checklist]
        lines.append("")
    if p.pitfalls:
        lines.append("## 常见坑")
        lines += [f"- {x}" for x in p.pitfalls]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
