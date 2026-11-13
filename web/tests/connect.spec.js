import { test, expect } from "@playwright/test";
const secret = "test-personal-connection-key";
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", {
      value: {
        writeText: async (text) => {
          window.copiedPrompt = text;
        },
      },
      configurable: true,
    });
  });
  await page.route("**/health", (route) =>
    route.fulfill({ json: { ok: true } }),
  );
  await page.route("**/api/v1/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    const data = path.endsWith("/auth/me")
      ? {
          user: {
            id: "test",
            display_name: "测试成员",
            username: "tester",
            role: "writer",
            status: "approved",
          },
        }
      : path.endsWith("/account/keys")
        ? { key: secret, keys: [] }
        : { documents: 1397, by_source: {} };
    return route.fulfill({ json: data });
  });
});

test("generates installation modes and keeps uploads opt-in", async ({
  page,
}) => {
  await page.goto("/#/connect");
  const preview = page.getByLabel("安装提示词预览");
  await expect(preview).toContainText("SHA-256:");
  await expect(preview).toContainText("team-knowledge-0.5.0.zip");
  await expect(preview).toContainText("YOUR_PERSONAL_KEY");
  await expect(preview).toContainText("不启用项目自动上传");
  await page
    .getByRole("button", { name: "复制安装提示词", exact: true })
    .click();
  expect(await page.evaluate(() => window.copiedPrompt)).toContain(
    "/static/downloads/v8_workbench",
  );
  await page.getByRole("button", { name: "仅 CLI", exact: false }).click();
  await expect(preview).not.toContainText("team-knowledge-0.5.0.zip");
  await expect(preview).not.toContainText('args=["mcp"]');
  await page.getByRole("button", { name: "仅 Skill", exact: false }).click();
  await expect(preview).toContainText("team-knowledge-0.5.0.zip");
  await expect(preview).not.toContainText('args=["mcp"]');
  await page.getByRole("button", { name: "仅 MCP", exact: false }).click();
  await expect(preview).toContainText('args=["mcp"]');
  await expect(preview).not.toContainText("team-knowledge-0.5.0.zip");
  await page.getByLabel("在当前开发项目启用经验候选提交").check();
  await expect(preview).toContainText("wb agent init --project");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("personal key is explicit, masked, copied and cleared on leaving", async ({
  page,
}) => {
  await page.goto("/#/connect");
  const input = page.getByLabel("已有个人 Key", { exact: true });
  await input.fill(secret);
  await page
    .getByRole("button", { name: "复制安装提示词", exact: true })
    .click();
  expect(await page.evaluate(() => window.copiedPrompt)).not.toContain(secret);
  await page.getByLabel("复制时包含个人 Key").check();
  await expect(page.getByLabel("安装提示词预览")).not.toContainText(secret);
  await page
    .getByRole("button", { name: "复制安装提示词", exact: true })
    .click();
  expect(await page.evaluate(() => window.copiedPrompt)).toContain(secret);
  expect(
    await page.evaluate(() =>
      JSON.stringify({ ...localStorage, ...sessionStorage }),
    ),
  ).not.toContain(secret);
  await page.getByRole("link", { name: "完整使用说明", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "使用说明", exact: true }),
  ).toBeVisible();
  await page.goto("/#/connect");
  await expect(input).toHaveValue("");
  await page.getByText("创建接入专用 Key", { exact: true }).click();
  await page.getByRole("button", { name: "创建并用于提示词" }).click();
  await expect(input).toHaveValue(secret);
  await expect(page.getByLabel("复制时包含个人 Key")).toBeChecked();
});

test("invalid download manifest blocks prompt generation and can retry", async ({
  page,
}) => {
  await page.route("**/static/downloads/manifest.json", (route) =>
    route.fulfill({ json: { sha256: {} } }),
  );
  await page.goto("/#/connect");
  await expect(page.getByRole("alert")).toContainText("校验信息尚未就绪");
  await expect(
    page.getByRole("button", { name: "复制安装提示词", exact: true }),
  ).toHaveCount(0);
  await page.unroute("**/static/downloads/manifest.json");
  await page.getByRole("button", { name: "重新加载", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "复制安装提示词", exact: true }),
  ).toBeEnabled();
});

test("new personal key can be handed to the installer without URL or storage", async ({
  page,
}) => {
  await page.goto("/#/account");
  await page.getByLabel("Key 名称").fill("本地安装测试");
  await page.getByRole("button", { name: "创建个人 Key", exact: true }).click();
  await page.getByRole("button", { name: "用此 Key 生成安装提示词 →" }).click();
  await expect(page.getByLabel("已有个人 Key", { exact: true })).toHaveValue(
    secret,
  );
  expect(page.url()).not.toContain(secret);
  await page.getByRole("button", { name: "选中提示词", exact: true }).click();
  const manual = page.getByLabel("手动复制安装提示词");
  await expect(manual).toBeFocused();
  await expect(manual).toHaveValue(new RegExp(secret));
  expect(
    await manual.evaluate((el) => el.selectionEnd - el.selectionStart),
  ).toBeGreaterThan(100);
});
