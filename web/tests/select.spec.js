import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("**/health", (r) => r.fulfill({ json: { ok: true } }));
  await page.route("**/api/v1/**", (r) => {
    const path = new URL(r.request().url()).pathname;
    let data = {};
    if (path.endsWith("/auth/me"))
      data = {
        user: {
          id: "test",
          username: "tester",
          display_name: "测试成员",
          status: "approved",
          role: "admin",
        },
      };
    if (path.endsWith("/categories"))
      data = {
        categories: Array.from({ length: 25 }, (_, i) => ({
          id: `cat-${i}`,
          path: `技术分类 ${String(i).padStart(2, "0")}`,
          name: `分类 ${i}`,
        })),
      };
    if (path.endsWith("/graph/all")) data = { nodes: [], edges: [] };
    return r.fulfill({ json: data });
  });
});
test("custom select supports keyboard selection, dismissal and focus restoration", async ({
  page,
}) => {
  await page.goto("/#/graph");
  const control = page.getByRole("combobox", { name: "知识链深度" });
  await control.focus();
  await control.press("ArrowDown");
  await expect(page.getByRole("listbox")).toBeVisible();
  await control.press("ArrowDown");
  await control.press("Enter");
  await expect(control).toHaveText("两跳关联");
  await expect(control).toBeFocused();
  await expect(control).toHaveAttribute("aria-expanded", "false");
  await control.click();
  await control.press("Escape");
  await expect(page.getByRole("listbox")).toHaveCount(0);
  await expect(control).toBeFocused();
  await control.click();
  await page.getByRole("heading", { name: "知识链", exact: true }).click();
  await expect(control).toHaveAttribute("aria-expanded", "false");
});
test("searchable options stay within the viewport and close when navigating", async ({
  page,
}) => {
  await page.goto("/#/graph");
  const control = page.getByRole("combobox", { name: "图谱分类范围" });
  await control.click();
  const search = page.getByRole("textbox", { name: "筛选选项" });
  await expect(search).toBeFocused();
  await search.fill("技术分类 24");
  await expect(page.getByRole("option")).toHaveCount(1);
  const bounds = await page.locator(".app-select-panel").boundingBox();
  const viewport = page.viewportSize();
  expect(bounds.x).toBeGreaterThanOrEqual(0);
  expect(bounds.x + bounds.width).toBeLessThanOrEqual(viewport.width);
  expect(bounds.y + bounds.height).toBeLessThanOrEqual(viewport.height);
  await search.press("Enter");
  await expect(control).toHaveText("技术分类 24");
  await control.click();
  await search.fill("不存在的分类");
  await expect(page.getByText("没有匹配的选项")).toBeVisible();
  await search.press("Escape");
  await expect(control).toBeFocused();
  await page
    .getByRole("link", { name: "浏览知识库", exact: true })
    .first()
    .click();
  await expect(page.locator(".route-page")).toHaveCount(1);
  await expect(page.locator(".route-page")).toBeVisible();
  await expect(page.getByRole("listbox")).toHaveCount(0);
});
test("reduced motion removes page and popover animation", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/#/graph");
  await page.getByRole("combobox", { name: "知识链深度" }).click();
  await expect(page.getByRole("listbox")).toBeVisible();
  const duration = await page
    .locator(".app-select-panel")
    .evaluate((e) => getComputedStyle(e).transitionDuration);
  expect(duration).toBe("0s");
});

test("page navigation mounts incoming content without waiting for an exit animation", async ({
  page,
}) => {
  await page.goto("/#/graph");
  await expect(
    page.getByRole("heading", { name: "知识链", exact: true }),
  ).toBeVisible();
  // Expose an accidental return to sequential out-in transitions.
  await page.addStyleTag({
    content: ".page-leave-active { transition: opacity 2s !important; }",
  });
  await page
    .getByRole("link", { name: "浏览知识库", exact: true })
    .first()
    .hover();
  await page.waitForTimeout(200);
  await page
    .getByRole("link", { name: "浏览知识库", exact: true })
    .first()
    .click();
  await expect(page.locator(".kb-library")).toBeVisible({ timeout: 1000 });
  await expect(page.locator(".route-page")).toHaveCount(1);
});
