import { test, expect } from "@playwright/test";
import { selectOption } from "./select-helper";
const categories = [
  {
    id: "technology",
    name: "技术开发",
    path: "技术开发",
    documents: 0,
    total_documents: 1,
  },
  {
    id: "backend",
    parent_id: "technology",
    name: "后端",
    path: "技术开发 / 后端",
    documents: 1,
  },
  { id: "uncategorized", name: "待分类", path: "待分类", documents: 0 },
];
test("分类浏览、草稿提交、审核与版本入口", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.addInitScript(() =>
    localStorage.setItem("v8wb_key", "test-admin"),
  );
  let contribution = null,
    published = false;
  const doc = {
    id: "kb:test",
    title: "连接池连接泄漏解决方案",
    content:
      "## 解决步骤\n\n使用事务作用域处理异常回滚并归还连接，并发验证连接数量恢复基线。",
    category_id: "backend",
    knowledge_version: 1,
    tags: ["数据库"],
    source: "agent",
    total_chars: 100,
    truncated: false,
  };
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url()),
      path = url.pathname.replace("/api/v1", ""),
      method = route.request().method();
    let data = {};
    if (path === "/auth/me")
      return route.fulfill({ status: 401, json: { message: "登录" } });
    if (path === "/stats")
      data = { documents: 1, by_domain: {}, by_source: {} };
    if (path === "/categories") data = { categories };
    if (path === "/library")
      data = {
        documents: published
          ? [
              {
                ...doc,
                summary: "经过实际验证的连接池修复方案",
                updated_at: 1700000000,
              },
            ]
          : [],
        total: published ? 1 : 0,
      };
    if (path === "/contributions" && method === "GET")
      data = {
        items: contribution ? [contribution] : [],
        total: contribution ? 1 : 0,
      };
    if (
      (path === "/contributions" && method === "POST") ||
      (path === "/contributions/con-test" && method === "PUT")
    ) {
      const body = route.request().postDataJSON();
      contribution = {
        ...body,
        id: "con-test",
        payload: body,
        status:
          url.searchParams.get("submit") === "false" ? "draft" : "pending",
        updated_at: 1700000000,
        events: [],
        similar: [],
        quality: { eligible: false },
      };
      data = contribution;
    }
    if (path === "/contributions/con-test" && method === "GET")
      data = contribution;
    if (path === "/contributions/con-test/review") {
      published = true;
      contribution = {
        ...contribution,
        status: "published",
        published_doc_id: doc.id,
      };
      data = contribution;
    }
    if (path === "/read") data = doc;
    if (path === "/versions/kb%3Atest" || path === "/versions/kb:test")
      data = {
        versions: [{ version: 1, actor: "test-admin", created_at: 1700000000 }],
      };
    if (path.endsWith("/1")) data = { ...doc, version: 1, actor: "test-admin" };
    await route.fulfill({ json: data });
  });
  await page.goto("/#/contribute");
  await page.getByRole("textbox", { name: "知识标题" }).fill(doc.title);
  await selectOption(page, page.getByLabel("知识分类"), "backend");
  await page.locator("#knowledge-content").fill(doc.content);
  await page.getByRole("button", { name: "保存草稿", exact: true }).click();
  await expect(page.locator(".success-banner")).toContainText("草稿已保存");
  await page.getByRole("button", { name: "提交审核", exact: true }).click();
  await expect(page.locator(".success-banner")).toContainText("已提交审核");
  await page.goto("/#/contributions");
  await page.locator(".kb-contribution").click();
  await expect(page.locator(".kb-review-detail")).toContainText(
    "使用事务作用域",
  );
  await page.goto("/#/review");
  await page.locator(".kb-contribution").click();
  await page.getByLabel("审核意见").fill("已核实验证结果");
  await page.getByRole("button", { name: "审核并发布" }).click();
  await expect(page.locator(".kb-review-detail")).toContainText("已发布");
  await page.goto("/#/library");
  await page
    .locator(".kb-taxonomy")
    .getByRole("button", { name: /后端/ })
    .click();
  await expect(page.locator(".kb-card")).toContainText(doc.title);
  await page.locator(".kb-card h3 a").click();
  await page.getByRole("button", { name: /版本历史/ }).click();
  await page.getByRole("button", { name: /v1 ·/ }).click();
  await expect(page.locator(".version-drawer")).toContainText("test-admin");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
});
