import { test, expect } from "@playwright/test";
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.removeItem("v8wb_key");
    window.__copied = "";
    Object.defineProperty(navigator, "clipboard", {
      value: {
        writeText: async (text) => {
          window.__copied = text;
        },
      },
      configurable: true,
    });
  });
  await page.route("**/health", (route) =>
    route.fulfill({ json: { ok: true, documents: 234 } }),
  );
  await page.route("**/api/v1/**", (route) =>
    new URL(route.request().url()).pathname.endsWith("/auth/me")
      ? route.fulfill({ status: 401, json: { message: "登录已失效" } })
      : route.fulfill({ json: { results: [], recent: [] } }),
  );
});
test("官网首页独立展示，工作台入口与预览检索可用", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /让知识流动/ })).toBeVisible();
  await expect(
    page.getByRole("complementary", { name: "工作台导航" }),
  ).toHaveCount(0);
  await expect(page.locator(".hero-bottom-stats")).toContainText("234");
  await page
    .locator(".preview-topic-switch")
    .getByRole("button", { name: "SPI 扩展", exact: true })
    .click();
  await expect(page.locator(".preview-search")).toContainText("SPI 扩展");
  await page.locator(".preview-search").click();
  await expect(page.getByRole("textbox", { name: "搜索知识库" })).toHaveValue(
    "SPI 扩展",
  );
  await expect(page).toHaveURL(/#\/workspace/);
  expect(errors).toEqual([]);
});
test("官网移动导航、FAQ和接入代码切换复制可用", async ({ page, isMobile }) => {
  await page.goto("/");
  if (isMobile)
    await page.getByRole("button", { name: "打开官网导航" }).click();
  const nav = page.getByRole("navigation", {
    name: isMobile ? "移动官网导航" : "官网导航",
  });
  await nav.getByRole("button", { name: "连接你的工具", exact: true }).click();
  await expect(page.locator("#integrations")).toBeInViewport();
  await page
    .locator(".integration-options")
    .getByRole("button", { name: /CLI/ })
    .click();
  await expect(page.locator(".code-window pre")).toContainText(
    "wb --json search",
  );
  await page.getByRole("button", { name: "复制 CLI 配置" }).click();
  expect(await page.evaluate(() => window.__copied)).toContain(
    "YOUR_PERSONAL_KEY",
  );
  await page
    .locator(".integration-options")
    .getByRole("button", { name: /Skill/ })
    .click();
  await expect(page.locator(".code-window pre")).toContainText(
    ".agents/skills",
  );
  await page.locator(".faq-list summary").first().click();
  await expect(page.locator(".faq-list details").first()).toHaveAttribute(
    "open",
    "",
  );
  await expect(
    page.locator(".faq-list details").first().locator("p"),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
test("官网和工作台互通，侧栏控制与旧检索链接兼容", async ({
  page,
  isMobile,
}) => {
  await page.goto("/");
  await page
    .locator(".site-header-actions")
    .getByRole("link", { name: "进入工作台" })
    .click();
  await expect(page.getByRole("textbox", { name: "搜索知识库" })).toBeVisible();
  if (isMobile) {
    await page.getByRole("button", { name: "打开导航" }).click();
    await expect(
      page.getByRole("dialog", { name: "工作台导航" }),
    ).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("button", { name: "打开导航" })).toBeFocused();
    await page.getByRole("button", { name: "打开导航" }).click();
  } else {
    await page.getByRole("button", { name: "收起侧栏" }).click();
    await expect(page.locator(".workspace")).toHaveClass(/sidebar-collapsed/);
    await page.reload();
    await expect(page.locator(".workspace")).toHaveClass(/sidebar-collapsed/);
    await page.getByRole("button", { name: "展开侧栏" }).click();
  }
  await page.getByRole("link", { name: "返回官网", exact: true }).click();
  await expect(page.getByRole("heading", { name: /让知识流动/ })).toBeVisible();
  await page.goto("/#/?q=组织同步");
  await expect(page.getByRole("textbox", { name: "搜索知识库" })).toHaveValue(
    "组织同步",
  );
  await expect(page).toHaveURL(/#\/workspace/);
});
test("官网跳转主内容不改变哈希路由，许可随构建发布", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await page.keyboard.press("Tab");
  await page.getByRole("link", { name: "跳转到主要内容" }).press("Enter");
  await expect(page.locator("#main")).toBeFocused();
  await expect(page.getByRole("heading", { name: /让知识流动/ })).toBeVisible();
  for (const name of [
    "shadcn-vue-landing-page",
    "shadcn-vue-admin",
    "tailadmin-vue",
  ]) {
    const response = await request.get(`/static/licenses/${name}.txt`);
    expect(response.ok()).toBe(true);
    expect(await response.text()).toContain("MIT License");
  }
});
