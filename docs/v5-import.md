# V5 内容导入与 CMP 抓取修复

`ingest/import_v5.py` 从 Skill 仓库的 `resources/docs/*_文档汇总.md` 导入，保持由站点和原始路由生成的文档 ID 稳定。标题下面只有“未能获取 Markdown”提示的条目会跳过，并计入 `fetch_failed_skipped`，防止把抓取错误作为知识发布。

CMP 各页面的实现不同，不能统一拼接 `md/fingerPost/<路由>.md`：

- 指南：`iframePhone/md/fingerPost/<名称>.md`。
- 调试详情：`iframePhone/md/inspect/<分组>_<名称>.md`；分组页应跟随官网重定向。
- 第三方集成详情：`iframePhone/md/third/<名称>.md`。
- 组件：Vue 渲染页面，内容来自 `iframePhone/source/<类型>/<名称>.js` 和 API 配置。
- 资源：Vue 渲染的下载列表，下载地址通过按钮的 `window.open` 提供。
- 部分页面使用 iframe，需要抓取 iframe 实际内容。

将待修复的原始路由数组存为 JSON 后，可以使用浏览器捕获页面：

```bash
node ingest/capture_cmp.mjs routes.json rendered.json
```

脚本依赖前端开发环境中的 Playwright 和 Chromium，展开嵌套参数表，保留示例代码，并将资源下载按钮转换为链接。抓取结果是供审查的 JSON，不会直接写数据库。

将已验证的 Markdown 快照（以路由为键，包含 `body`、`url`、`sources`）与页面捕获合并：

```bash
.venv/bin/pip install 'markdownify>=1.2,<2'
.venv/bin/python ingest/prepare_cmp_snapshot.py --markdown direct.json --capture rendered.json --output recovered.json
.venv/bin/python ingest/import_v5.py --skill-dir /path/to/seeyon-kk-skill --cmp-snapshot recovered.json --dry-run
```

去掉 `--dry-run` 后才写入数据库，应先使用 SQLite backup API 备份生产库。线上服务使用内存索引，导入后需要调用管理员 `POST /api/v1/admin/rebuild`。

2026-11-13 修复了 122 条 CMP 抓取失败记录。官网已移除的 `/inspect/m3debugAndroid/debugm3` 保留历史并下架。生产修复快照保存在 `/var/lib/v8wb/imports/cmp-recovered-20261113.json`，来源版本为 `497f5231f945750f470918fbd52ef3e4229dcb7d`。
