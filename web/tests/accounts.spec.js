import { test, expect } from "@playwright/test";
const pendingUser = {
  id: "u1",
  username: "alice",
  display_name: "Alice",
  status: "pending",
  role: "reader",
  review_note: "",
  created_at: 1700000000,
};
const stats = {
  documents: 234,
  terms: 28755,
  by_domain: { 开发规范: 24 },
  by_source: { yuque: 234 },
};
async function mockApp(
  page,
  {
    signedIn = false,
    legacy = false,
    status = "approved",
    role = "writer",
  } = {},
) {
  let user = { ...pendingUser, status, role },
    loggedIn = signedIn,
    keys = [],
    applicants = [{ ...pendingUser }];
  await page.addInitScript((legacy) => {
    localStorage.removeItem("v8wb_key");
    if (legacy) localStorage.setItem("v8wb_key", "test-legacy-admin");
  }, legacy);
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", ""),
      method = route.request().method();
    let data = {},
      code = 200;
    if (path === "/auth/me") {
      data = loggedIn ? { user } : { message: "请登录" };
      if (!loggedIn) code = 401;
    }
    if (path === "/auth/register") {
      user = { ...pendingUser };
      data = { user };
      code = 201;
    }
    if (path === "/auth/login") {
      loggedIn = true;
      data = { user };
    }
    if (path === "/auth/logout" || path === "/auth/password") {
      loggedIn = false;
      data = { ok: true };
    }
    if (path === "/stats") data = stats;
    if (path === "/recent") data = { recent: [] };
    if (path === "/account/keys") {
      if (method === "POST") {
        const body = route.request().postDataJSON();
        keys.push({
          name: body.name,
          role: body.role,
          key_prefix: "wr_test",
          enabled: true,
          used_today: 0,
          daily_limit: 20000,
        });
        data = { key: "test-personal-secret-once" };
        code = 201;
      } else data = { keys };
    }
    if (path.startsWith("/account/keys/")) {
      keys = keys.map((k) => ({ ...k, enabled: false }));
      data = { revoked: true };
    }
    if (path === "/admin/users") data = { users: applicants };
    if (path.startsWith("/admin/users/")) {
      const body = route.request().postDataJSON();
      applicants = applicants.map((u) => ({ ...u, ...body }));
      data = { user: applicants[0] };
    }
    if (path === "/admin/keys") data = { keys: [] };
    if (path === "/admin/usage") data = { usage: [] };
    await route.fulfill({ status: code, json: data });
  });
}
async function navigate(page, label, mobile) {
  if (mobile) await page.getByRole("button", { name: "打开导航" }).click();
  await page
    .getByRole("navigation")
    .getByRole("link", { name: label, exact: true })
    .click();
}
test("注册后显示待审批，不允许创建个人 Key", async ({ page }) => {
  await mockApp(page);
  await page.goto("/#/register");
  await page.getByRole("textbox", { name: "姓名 / 显示名称" }).fill("Alice");
  await page
    .getByRole("textbox", { name: "用户名", exact: true })
    .fill("alice");
  await page
    .getByRole("textbox", { name: "密码", exact: true })
    .fill("my-test-password-123");
  await page
    .getByRole("textbox", { name: "确认密码", exact: true })
    .fill("my-test-password-123");
  await page.getByRole("button", { name: "注册并申请入网" }).click();
  await expect(
    page.getByRole("heading", { name: "注册成功，等待管理员审批" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "创建个人 Key" })).toHaveCount(
    0,
  );
  await expect(page.getByRole("button", { name: "刷新状态" })).toBeVisible();
});
test("账号登录后只能选择获准角色，个人 Key 可创建和吊销", async ({ page }) => {
  await mockApp(page);
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/#/login");
  await page
    .getByRole("textbox", { name: "用户名", exact: true })
    .fill("alice");
  await page
    .getByRole("textbox", { name: "密码", exact: true })
    .fill("my-test-password-123");
  await page.getByRole("button", { name: "登录工作台" }).click();
  await expect(
    page.getByRole("heading", { name: "我的 API Key" }),
  ).toBeVisible();
  await expect(
    page.getByRole("combobox", { name: "Key 权限" }).locator("option"),
  ).toHaveCount(2);
  await page.getByRole("textbox", { name: "Key 名称" }).fill("我的 Codex");
  await page.getByRole("combobox", { name: "Key 权限" }).selectOption("writer");
  await page.getByRole("button", { name: "创建个人 Key" }).click();
  await expect(page.locator(".new-key-box")).toContainText(
    "test-personal-secret-once",
  );
  await expect(page.locator("table")).toContainText("我的 Codex");
  await page.getByRole("button", { name: "吊销", exact: true }).click();
  await page
    .getByRole("dialog", { name: "确认操作" })
    .getByRole("button", { name: "确认", exact: true })
    .click();
  await expect(page.locator("table")).toContainText("已吊销");
  await page.getByRole("button", { name: "退出登录" }).click();
  await expect(page.getByRole("button", { name: "登录工作台" })).toBeVisible();
  expect(errors).toEqual([]);
});
test("管理员审批入网并可停用账号", async ({ page }) => {
  await mockApp(page, { legacy: true });
  await page.goto("/#/admin");
  await expect(
    page.getByRole("heading", { name: "账号审批与管理" }),
  ).toBeVisible();
  await page
    .getByRole("textbox", { name: "审批说明 alice" })
    .fill("已核实成员身份");
  await page.getByRole("button", { name: "批准入网" }).click();
  await expect(page.locator(".toast")).toContainText("账号状态已更新");
  await page
    .locator(".account-approvals")
    .getByRole("button", { name: "已入网", exact: true })
    .click();
  await expect(page.locator(".approval-card")).toContainText("Alice");
  await page.getByRole("button", { name: "停用账号" }).click();
  await page
    .getByRole("dialog", { name: "确认操作" })
    .getByRole("button", { name: "确认", exact: true })
    .click();
  await page
    .locator(".account-approvals")
    .getByRole("button", { name: "已停用", exact: true })
    .click();
  await expect(page.locator(".approval-card")).toContainText("已停用");
});
test("使用说明覆盖三种接入方式，支持下载且无横向溢出", async ({
  page,
  isMobile,
}) => {
  await mockApp(page);
  await page.goto("/#/guide?section=1.5");
  await expect(page.locator(".guide-body")).toContainText("一键接入本地 Agent");
  await page
    .getByRole("button", { name: "平台使用：分类、审核与版本", exact: true })
    .click();
  await expect(page.locator(".guide-body")).toContainText(
    "平台使用：分类、审核与版本",
  );
  await expect(
    page.getByRole("heading", { name: "使用说明", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "3. MCP 安装与接入", exact: true })
    .click();
  await expect(page.locator(".guide-body")).toContainText("stdio");
  await expect(page.locator(".guide-body")).toContainText("env_vars");
  await page
    .getByRole("button", { name: "4. Skill 安装与使用", exact: true })
    .click();
  await expect(page.locator(".guide-body")).toContainText(".agents/skills");
  await page
    .getByRole("button", { name: "5. CLI 常用命令", exact: true })
    .click();
  await expect(page.locator(".guide-body")).toContainText("wb --json search");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  if (!isMobile) {
    const download = page.waitForEvent("download");
    await page.getByRole("link", { name: "下载完整文档" }).click();
    expect((await download).suggestedFilename()).toContain("使用说明");
  }
});
test("密码修改后退回登录页", async ({ page }) => {
  await mockApp(page, { signedIn: true });
  await page.goto("/#/account");
  await page.getByText("修改登录密码", { exact: true }).click();
  await page
    .getByRole("textbox", { name: "当前密码", exact: true })
    .fill("my-test-password-123");
  await page
    .getByRole("textbox", { name: "新密码", exact: true })
    .fill("new-test-password-123");
  await page
    .getByRole("textbox", { name: "确认新密码", exact: true })
    .fill("new-test-password-123");
  await page.getByRole("button", { name: "修改并重新登录" }).click();
  await expect(page.getByRole("button", { name: "登录工作台" })).toBeVisible();
});
