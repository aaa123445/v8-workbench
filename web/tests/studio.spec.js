import { test, expect } from "@playwright/test";
import { selectOption } from "./select-helper";
const doc = {
  id: "kb:ui",
  title: "连接池排查与验证方案",
  category_id: "backend",
  category_path: "技术开发 / 后端",
  path: "技术开发 > 后端",
  knowledge_version: 1,
  tags: ["数据库"],
  source: "manual",
  summary: "通过事务回滚与连接归还，避免异常路径耗尽连接池。",
  updated_at: 1700000000,
  content:
    "## 问题背景\n\n异常路径出现连接泄漏。\n\n## 解决方案\n\n```js\nconst rollback = true\n```\n\n## 验证结果\n\n连接池计数恢复到基线。",
  total_chars: 120,
  truncated: false,
};
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("v8wb_key", "test-ui-only");
    Object.defineProperty(navigator, "clipboard", {
      value: {
        writeText: async (text) => {
          window.__copied = text;
        },
      },
      configurable: true,
    });
  });
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url()),
      path = url.pathname.replace("/api/v1", "");
    let data = {};
    if (path === "/auth/me")
      return route.fulfill({ status: 401, json: { message: "未登录" } });
    if (path === "/categories")
      data = {
        categories: [
          {
            id: "technology",
            name: "技术开发",
            path: "技术开发",
            documents: 0,
            total_documents: 1,
          },
          {
            id: "backend",
            name: "后端",
            parent_id: "technology",
            path: "技术开发 / 后端",
            documents: 1,
          },
        ],
      };
    if (path === "/stats")
      data = { documents: 1, by_domain: {}, by_source: { manual: 1 } };
    if (path === "/library") data = { documents: [doc], total: 1 };
    if (path === "/search")
      data = { query: "连接池", results: [doc], count: 1 };
    if (path === "/read") data = doc;
    if (path === "/contributions" && route.request().method() === "POST")
      data = { id: "con-ui", status: "draft", action: "created" };
    await route.fulfill({ json: data });
  });
});
test("全局快捷搜索支持键盘选择、打开结果与焦点恢复", async ({ page }) => {
  await page.goto("/#/library");
  const trigger = page.getByRole("button", { name: "打开全局搜索" });
  await trigger.click();
  await expect(
    page.getByRole("textbox", { name: "全局搜索关键词" }),
  ).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(trigger).toBeFocused();
  await page.keyboard.press("Control+k");
  await page.getByRole("textbox", { name: "全局搜索关键词" }).fill("连接池");
  await expect(page.locator(".command-result")).toContainText(doc.title);
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Enter");
  await expect(page.locator(".reader h1")).toHaveText(doc.title);
  await expect(page.getByRole("dialog", { name: "全局知识搜索" })).toHaveCount(
    0,
  );
});
test("知识视图持久保存，筛选可清除且排序发送到服务器", async ({ page }) => {
  await page.goto("/#/library");
  await page.getByRole("button", { name: "列表视图", exact: true }).click();
  await expect(page.locator(".kb-cards")).toHaveClass(/is-list/);
  await page.reload();
  await expect(page.locator(".kb-cards")).toHaveClass(/is-list/);
  const request = page.waitForRequest(
    (r) =>
      r.url().includes("/library?") &&
      new URL(r.url()).searchParams.get("sort") === "title",
  );
  await selectOption(
    page,
    page.getByRole("combobox", { name: "知识排序" }),
    "title",
  );
  await request;
  await page.getByRole("textbox", { name: "筛选知识" }).fill("事务");
  await expect(page).toHaveURL(/q=/);
  await page.getByRole("button", { name: "清除知识筛选" }).click();
  await expect(page).not.toHaveURL(/q=/);
  await page.getByRole("button", { name: "卡片视图", exact: true }).click();
  await expect(page.locator(".kb-cards")).not.toHaveClass(/is-list/);
});
test("编辑工具栏、草稿快捷键与离开确认可用", async ({ page }) => {
  await page.goto("/#/contribute");
  await page
    .getByRole("textbox", { name: "知识标题" })
    .fill("一个真实验证过的解决方案");
  await page
    .locator("#knowledge-content")
    .fill(
      "这是完整的问题背景、具体解决步骤与验证结果，足以被团队中的其他人理解并再次复用。",
    );
  await page.getByRole("button", { name: "加粗文字", exact: true }).click();
  await expect(page.locator("#knowledge-content")).toHaveValue(
    /\*\*加粗文字\*\*/,
  );
  await page.keyboard.press("Control+s");
  await expect(page.locator(".success-banner")).toContainText("草稿已保存");
  await page
    .locator("#knowledge-content")
    .fill(
      "修改后的解决方案还没有保存，应该在离开当前编辑器时出现可取消的确认。",
    );
  await page.getByRole("link", { name: "我的贡献 →", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "离开编辑器？" });
  await expect(dialog).toBeVisible();
  await page.keyboard.press("Control+k");
  await expect(page.getByRole("dialog", { name: "全局知识搜索" })).toHaveCount(
    0,
  );
  await expect(dialog).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(page.locator("#knowledge-content")).toBeVisible();
});
test("阅读目录不改变路由，代码块可复制", async ({ page, isMobile }) => {
  await page.goto("/#/documents/kb%3Aui");
  await expect(page.locator(".reader h1")).toHaveText(doc.title);
  await page.getByRole("button", { name: "复制代码块" }).click();
  expect(await page.evaluate(() => window.__copied)).toContain(
    "const rollback = true",
  );
  if (!isMobile) {
    const url = page.url();
    await page
      .getByRole("navigation", { name: "文档目录" })
      .getByRole("button", { name: "验证结果" })
      .click();
    expect(page.url()).toBe(url);
    await expect(
      page.getByRole("heading", { name: "验证结果", exact: true }),
    ).toBeFocused();
  }
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("版本恢复的确认框位于抽屉上层，恢复后正确刷新", async ({ page }) => {
  let currentVersion = 2;
  await page.route("**/api/v1/read", (route) =>
    route.fulfill({ json: { ...doc, knowledge_version: currentVersion } }),
  );
  await page.route("**/api/v1/versions/**", async (route) => {
    const path = decodeURIComponent(new URL(route.request().url()).pathname);
    if (path.endsWith("/rollback")) {
      expect(route.request().postDataJSON().expected_version).toBe(2);
      currentVersion = 3;
      return route.fulfill({ json: { id: doc.id, version: 3 } });
    }
    if (path.endsWith("/1"))
      return route.fulfill({
        json: { ...doc, version: 1, actor: "test-admin" },
      });
    return route.fulfill({
      json: {
        versions: [
          { version: 2, created_at: 1700001000 },
          { version: 1, created_at: 1700000000 },
        ],
      },
    });
  });
  await page.goto("/#/documents/kb%3Aui");
  await page.getByRole("button", { name: /版本历史/ }).click();
  await page.getByRole("button", { name: /v1 ·/ }).click();
  await page.getByRole("button", { name: "恢复此版本" }).click();
  const confirm = page.getByRole("dialog", { name: "恢复历史版本？" });
  await expect(
    confirm.getByRole("button", { name: "取消", exact: true }),
  ).toBeFocused();
  await confirm.getByRole("button", { name: "确认恢复" }).click();
  await expect(
    page.getByRole("button", { name: /版本历史.*v3/ }),
  ).toBeVisible();
  await expect(page.getByRole("dialog", { name: "文档版本历史" })).toHaveCount(
    0,
  );
  expect(await page.evaluate(() => document.body.style.overflow)).not.toBe(
    "hidden",
  );
});
