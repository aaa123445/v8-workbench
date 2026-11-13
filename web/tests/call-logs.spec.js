import { test, expect } from "@playwright/test";
import { selectOption } from "./select-helper";
const entries = Array.from({ length: 25 }, (_, i) => ({
  id: 100 + i,
  operation: i % 3 === 0 ? "read" : "search",
  client: i % 2 ? "cli" : "mcp",
  credential_kind: "key",
  credential_name: "我的 Agent",
  key_prefix: i % 2 ? "wr_cli123" : "wr_mcp123",
  request_summary: i === 0 ? "组织同步开发指南" : "组织同步 " + i,
  result_summary: i === 0 ? "未找到文档：missing" : "命中 2 篇文档",
  status_code: i === 0 ? 400 : 200,
  outcome: i === 0 ? "failed" : "success",
  duration_ms: 12.5 + i,
  request_truncated: false,
  response_truncated: i === 1,
  ts: 1794501000 - i * 60,
}));
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.removeItem("v8wb_key"));
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url()),
      path = url.pathname.replace("/api/v1", "");
    let data = {};
    if (path === "/auth/me")
      data = {
        user: {
          id: "alice",
          username: "alice",
          display_name: "Alice",
          status: "approved",
          role: "writer",
        },
      };
    if (path === "/stats")
      data = { documents: 234, terms: 1000, by_domain: {}, by_source: {} };
    if (path === "/account/calls") {
      let logs = entries.filter(
        (row) =>
          (!url.searchParams.get("query") ||
            row.request_summary.includes(url.searchParams.get("query"))) &&
          ["operation", "client", "outcome", "key_prefix"].every(
            (key) =>
              !url.searchParams.get(key) ||
              row[key] === url.searchParams.get(key),
          ),
      );
      const total = logs.length,
        pageSize = Number(url.searchParams.get("page_size") || 20),
        page = Number(url.searchParams.get("page") || 1);
      data = {
        logs: logs.slice((page - 1) * pageSize, page * pageSize),
        total,
        page,
        page_size: pageSize,
        summary: {
          total,
          success: logs.filter((r) => r.outcome === "success").length,
          failed: logs.filter((r) => r.outcome === "failed").length,
          partial: 0,
          avg_duration_ms: 23.1,
        },
        keys: ["wr_cli123", "wr_mcp123"],
        scope: "account",
        retention_days: 30,
        max_entries: 2000,
      };
    }
    if (/^\/account\/calls\/\d+$/.test(path)) {
      const row = entries.find((r) => r.id === Number(path.split("/").at(-1)));
      data = {
        ...row,
        method: "POST",
        path: "/api/v1/" + row.operation,
        request: { query: "组织同步", api_key: "[已隐藏]" },
        response:
          row.outcome === "failed"
            ? { error: "not_found", message: "未找到文档：missing" }
            : {
                count: 2,
                results: [
                  {
                    title: "组织同步",
                    content: "<script>window.bad=true</script>",
                  },
                ],
              },
      };
    }
    await route.fulfill({ json: data });
  });
});
test("个人日志统计、分页与筛选正常", async ({ page }) => {
  await page.goto("/#/account/logs");
  await expect(
    page.getByRole("heading", { name: "我的调用日志", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".call-log-stats").first()).toContainText("25");
  await page.getByRole("button", { name: "下一页日志" }).click();
  await expect(page.locator(".call-log-pagination")).toContainText(
    "第 2 / 2 页",
  );
  await selectOption(
    page,
    page.getByRole("combobox", { name: "调用状态", exact: true }),
    "failed",
  );
  await expect(page.locator(".call-log-list .badge").first()).toHaveText(
    "1 条",
  );
  await expect(page.locator(".call-log-pagination")).toContainText(
    "第 1 / 1 页",
  );
  await page.getByRole("button", { name: "重置", exact: true }).click();
  await selectOption(
    page,
    page.getByRole("combobox", { name: "调用来源", exact: true }),
    "cli",
  );
  await expect(page.locator(".call-log-list .badge").first()).toHaveText(
    "12 条",
  );
  await page.getByRole("textbox", { name: "搜索调用日志" }).fill("组织同步 1");
  await page.getByRole("button", { name: "查询", exact: true }).click();
  await expect(page.locator(".call-log-list .badge").first()).toHaveText(
    "6 条",
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
test("调用详情安全显示请求与返回结果，关闭后焦点恢复", async ({
  page,
  isMobile,
}) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/#/account/logs");
  const details = page
    .getByRole("button", { name: "查看调用 100 详情" })
    .filter({ visible: true });
  await details.click();
  const dialog = page.getByRole("dialog", { name: "调用详情", exact: true });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByLabel("返回结果快照")).toContainText(
    "未找到文档：missing",
  );
  await dialog.getByRole("button", { name: "请求参数", exact: true }).click();
  await expect(dialog.getByLabel("请求参数快照")).toContainText("[已隐藏]");
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(details).toBeFocused();
  await page
    .getByRole("button", { name: "查看调用 101 详情" })
    .filter({ visible: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText("仅保留截断快照");
  await expect(page.locator(".call-snapshot script")).toHaveCount(0);
  expect(await page.evaluate(() => window.bad)).toBeUndefined();
  await page.screenshot({
    path: `test-results/call-log-detail-${isMobile ? "mobile" : "desktop"}.png`,
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
test("个人中心与侧栏均可进入日志页面", async ({ page, isMobile }) => {
  await page.goto("/#/account");
  await page
    .locator(".page-heading")
    .getByRole("link", { name: "我的调用日志" })
    .click();
  await expect(
    page.getByRole("heading", { name: "我的调用日志", exact: true }),
  ).toBeVisible();
  if (isMobile) await page.getByRole("button", { name: "打开导航" }).click();
  await page
    .getByRole("navigation", { name: "连接与管理" })
    .getByRole("link", { name: "我的调用日志", exact: true })
    .click();
  await expect(page.locator(".call-log-list")).toBeVisible();
});
test("匿名用户只显示登录入口，不读取个人日志", async ({ page }) => {
  let calls = 0;
  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({ status: 401, json: { message: "请登录" } }),
  );
  await page.route("**/api/v1/account/calls*", (route) => {
    calls++;
    return route.fulfill({ json: {} });
  });
  await page.goto("/#/account/logs");
  await expect(
    page.getByRole("heading", { name: "登录后查看个人调用日志" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "账号登录", exact: true }),
  ).toBeVisible();
  expect(calls).toBe(0);
});
