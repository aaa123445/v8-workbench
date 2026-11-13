import { test, expect } from "@playwright/test";
const stats = {
  documents: 234,
  terms: 8600,
  by_domain: { 开发规范: 24, 扩展能力: 60 },
  by_source: { yuque: 230, manual: 4 },
};
const doc = {
  id: "yuque:123",
  title: "组织同步中间表开发指南",
  source: "yuque",
  domain: "扩展能力",
  path: "扩展能力 > 组织同步",
  content:
    '# 组织同步\n\n开发指南正文。\n\n```js\nconst sync = true\n```\n\n<img src=x onerror="window.xssTriggered=true">\n\n<script>window.xssTriggered=true</script>',
  total_chars: 100,
  truncated: true,
  next_offset: 100,
  url: "https://www.yuque.com/test",
  score: 12.3,
};
async function navigate(page, label, mobile) {
  if (mobile) await page.getByRole("button", { name: "打开导航" }).click();
  await page
    .getByRole("navigation")
    .getByRole("link", { name: label, exact: true })
    .click();
}
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() =>
    localStorage.setItem("v8wb_key", "test-only-key"),
  );
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url()),
      path = url.pathname.replace("/api/v1", "");
    let data = {};
    if (path === "/admin/users") data = { users: [] };
    if (path === "/stats") data = stats;
    if (path === "/recent") data = { recent: [doc] };
    if (path === "/search") data = { results: [doc], count: 1 };
    if (path === "/read")
      data = route.request().postDataJSON().offset
        ? {
            ...doc,
            content: "\n\n后续文档内容",
            truncated: false,
            next_offset: null,
          }
        : doc;
    if (path === "/categories")
      data = {
        categories: [
          {
            id: "backend",
            name: "后端",
            path: "技术开发 / 后端",
            documents: 1,
          },
        ],
      };
    if (path === "/standards")
      data = {
        standards: [
          {
            id: "standard-1",
            name: "团队开发规范",
            category_id: "backend",
            description: "开发前先确认接口签名",
            checklist: ["确认接口签名", "验证扩展行为"],
            doc_ids: [doc.id],
          },
        ],
      };
    if (path === "/rules")
      data = {
        name: "SPI 扩展规范",
        profile: "spi",
        checklist: ["确认接口签名", "验证扩展行为"],
        pitfalls: ["避免修改平台源码"],
        documents_index: [doc],
      };
    if (path === "/contributions")
      data = {
        id: "con-test",
        title: "测试知识",
        action: "created",
        status: "pending",
      };
    if (path === "/knowledge")
      data = { id: doc.id, title: "测试知识", action: "created" };
    if (path === "/admin/keys")
      data =
        route.request().method() === "POST"
          ? { key: "test-new-key-once" }
          : {
              keys: [
                {
                  name: "开发测试",
                  key_prefix: "test-prefix",
                  role: "writer",
                  used_today: 12,
                  daily_limit: 1000,
                  enabled: true,
                },
              ],
            };
    if (path.startsWith("/admin/keys/")) data = { revoked: true };
    if (path === "/admin/usage") data = { usage: [] };
    if (path === "/admin/sync/yuque")
      data = {
        created: 2,
        updated: 1,
        failed: 1,
        errors: [{ title: "受限文档", error: "403" }],
      };
    if (path === "/admin/rebuild") data = { indexed: 234 };
    await route.fulfill({ json: data });
  });
});
test("检索、阅读、长文续读与 Markdown 安全", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/#/workspace");
  await expect(
    page.getByRole("heading", { name: "让开发有据可循." }),
  ).toBeVisible();
  await page.getByRole("textbox", { name: "搜索知识库" }).fill("组织同步");
  await page.getByRole("button", { name: "搜索知识", exact: true }).click();
  await expect(page.getByRole("heading", { name: "检索结果" })).toBeVisible();
  await page.locator(".doc-card").first().click();
  await expect(page.locator(".reader h1").first()).toHaveText(doc.title);
  await expect(page.locator(".prose pre")).toContainText("const sync = true");
  await expect(page.locator(".prose script")).toHaveCount(0);
  expect(await page.evaluate(() => window.xssTriggered)).toBeUndefined();
  await page.getByRole("button", { name: "加载后续内容" }).click();
  await expect(page.locator(".prose")).toContainText("后续文档内容");
  expect(errors).toEqual([]);
});
test("页面导航、清单与移动端无横向溢出", async ({ page, isMobile }) => {
  await page.goto("/#/workspace");
  await navigate(page, "团队规范", isMobile);
  await expect(page.getByText("确认接口签名", { exact: true })).toBeVisible();
  await expect(page.getByText("验证扩展行为", { exact: true })).toBeVisible();
  await navigate(page, "知识总览", isMobile);
  await expect(page.locator(".stat-card").first()).toContainText("234");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await navigate(page, "知识检索", isMobile);
  await page.screenshot({
    path: `test-results/home-${isMobile ? "mobile" : "desktop"}.png`,
    fullPage: true,
  });
});
test("知识编辑预览、保存与 Key 创建结果保留", async ({ page, isMobile }) => {
  await page.goto("/#/contribute");
  await page.getByRole("textbox", { name: "知识标题" }).fill("测试知识");
  await page
    .locator("#knowledge-content")
    .fill(
      "## 排查经验\n\n这是一条包含场景和具体解决步骤的开发经验，用于验证表单和预览。",
    );
  await page.getByRole("button", { name: "预览", exact: true }).click();
  await expect(page.locator(".editor-preview h2")).toHaveText("排查经验");
  await page.getByRole("button", { name: "提交审核" }).click();
  await expect(page.locator(".success-banner")).toContainText("已提交审核");
  await navigate(page, "工作台管理", isMobile);
  await page.getByRole("textbox", { name: "Key 名称" }).fill("测试 Agent");
  await page.getByRole("button", { name: "创建 Key" }).click();
  await expect(page.locator(".new-key-box")).toContainText("test-new-key-once");
  await page.getByRole("button", { name: "重建检索索引" }).click();
  await expect(page.locator(".toast")).toContainText("234");
  await page.getByRole("button", { name: "同步语雀知识库" }).click();
  await expect(page.locator(".sync-report")).toContainText("新增 2");
  await page.getByRole("button", { name: "吊销", exact: true }).click();
  await page
    .getByRole("dialog", { name: "确认操作" })
    .getByRole("button", { name: "确认", exact: true })
    .click();
  await expect(page.locator(".toast")).toContainText("Key 已吊销");
});
test("鉴权错误可恢复并可更换 Key", async ({ page }) => {
  await page.route("**/api/v1/search", (route) =>
    route.fulfill({ status: 401, json: { detail: {} } }),
  );
  await page.goto("/?test=1#/workspace");
  await page.getByRole("textbox", { name: "搜索知识库" }).fill("测试");
  await page.getByRole("button", { name: "搜索知识", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("API Key");
  await page.getByRole("button", { name: "配置 Key", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page
    .getByRole("textbox", { name: "API Key", exact: true })
    .fill("new-test-key");
  await page.getByRole("button", { name: "验证并连接" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(await page.evaluate(() => localStorage.getItem("v8wb_key"))).toBe(
    "new-test-key",
  );
});
