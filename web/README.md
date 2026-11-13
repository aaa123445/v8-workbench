# TeamKB 前端

Vue 3 Composition API + Vue Router + Vite。静态资源与 API 同源，不依赖外部 CDN。使用 hash 路由，刷新或分享文档链接无需额外的 nginx SPA 配置。

## 开发

需要 Node.js 20.19+ 或 22.12+。

```bash
cd web
npm ci
npm run dev
```

打开终端显示的 `/static/` 开发地址。`/api` 与 `/health` 代理至本机 80 端口；可在 `vite.config.js` 中调整后端地址。

## 模块

- `src/layouts/PublicLayout.vue`：官网与登录注册使用的公共布局。
- `src/layouts/WorkspaceLayout.vue`：后台侧栏、页头、状态与内容布局。
- `src/views/`：官网首页、检索、文档阅读、开发规范、经验沉淀、知识总览、账号与管理。
- `src/components/site/`：官网首屏、工作流预览、功能卡片、步骤、接入方式、FAQ、导航与页脚。
- `src/components/ui/`：共享品牌和卡片基础组件。
- `src/components/`：Key 对话框、文档卡片、异步状态、安全 Markdown 渲染。
- `src/services/api.js`：请求、鉴权和错误处理。
- `src/composables/`：共享凭据、统计、通知和带竞态保护的数据加载。
- `src/router.js`：路由与按页面分包。
- `src/styles.css`：设计变量、基础控件、弹窗与公共状态。
- `src/styles/workspace.css`：后台布局与响应式侧栏。
- `src/styles/pages.css`：业务页面样式。
- `src/styles/marketing.css`：官网页面样式。

Key 沿用旧版的 `v8wb_key` localStorage 存储项。接口权限仍由后端校验。Markdown 经 DOMPurify 过滤后渲染。

## 构建与部署

```bash
# 仅构建：输出 web/dist
npm run build
# 线上更新：在仓库根目录拉取代码后执行
sudo bash deploy/update.sh
```

更新脚本在独立目录完成构建，成功后发布，保留旧哈希资源供已打开页面使用；不覆盖管理员 Key、数据库或 HTTPS 配置。`deploy/install.sh` 用于首次安装，会生成初始 Key，日常更新不要重复执行。Dockerfile 使用 Node 构建阶段，Python 运行镜像仅包含构建产物。

FastAPI 从 `web/dist` 提供首页与 `/static` 资源，首次启动前必须先构建前端。

## 浏览器回归

```bash
npx playwright install chromium
npm run test:e2e
```

默认访问本机线上服务 `http://127.0.0.1`，也可通过 `E2E_BASE_URL` 指定独立测试服务。测试使用拦截的接口数据，不会写入线上知识库或创建、吊销真实 Key。

## 官网与模板

网站根路由 `/#/` 为官网首页；`/#/workspace` 为知识工作台，`/#/search` 是兼容别名。已有的 `/#/?q=关键词` 检索链接会跳转到工作台并保留查询参数。账号、文档阅读、审批和使用说明路由继续有效。

官网与后台分别适配 MIT 许可的 [Shadcn/Vue Landing Page](https://github.com/leoMirandaa/shadcn-vue-landing-page) 和 [Shadcn Vue Admin](https://github.com/Whbbit1999/shadcn-vue-admin)。参考提交、使用范围与版权说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。完整许可保存在 `public/licenses/`，构建时发布至 `/static/licenses/`。

模板仅用于界面与布局。官网展示的文档总数来自公开的 `/health`；产品预览明确为工作流示意，示例不包含客户信息。MCP、Skill、CLI 配置示例使用占位符，不读取个人 Key。
