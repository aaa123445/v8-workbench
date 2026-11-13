import { test, expect } from "@playwright/test";
const categories = [{ id: "backend", name: "后端", path: "技术开发 / 后端" }];
const nodes = [
  {
    id: "doc:one",
    title: "连接池故障排查",
    category_id: "backend",
    knowledge_version: 2,
  },
  {
    id: "doc:two",
    title: "事务回滚方案",
    category_id: "backend",
    knowledge_version: 1,
  },
];
const edges = [
  {
    id: "edge1",
    source_id: "doc:one",
    target_id: "doc:two",
    kind: "solution",
    label: "问题与解法",
    origin: "manual",
    actor: "user:test",
  },
];
test.beforeEach(async ({ page }) => {
  await page.route("**/health", (r) =>
    r.fulfill({ json: { ok: true, documents: 2 } }),
  );
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
          role: "writer",
        },
      };
    if (path.endsWith("/categories")) data = { categories };
    if (path.endsWith("/stats"))
      data = { documents: 2, by_source: { manual: 2 } };
    if (path.endsWith("/search")) data = { results: nodes, count: 2 };
    if (path.endsWith("/graph") || path.endsWith("/graph/all"))
      data = {
        center: "doc:one",
        nodes,
        edges,
        suggestions: [
          { id: "doc:three", title: "部署连接池", reason: "标题关键词匹配" },
        ],
        categories,
      };
    if (path.endsWith("/assistant/status"))
      data = { ready: true, enabled: true, model: "test-model" };
    if (path.endsWith("/assistant/ask"))
      data = {
        answer: "先检查连接池状态[1]，再确认回滚行为[2]。",
        scenario: "troubleshoot",
        mode: "chain",
        status: "answered",
        model: "test-model",
        citations: nodes.map((n, i) => ({
          ...n,
          number: i + 1,
          version: n.knowledge_version,
          excerpt: "已发布知识的验证资料",
          truncated: true,
        })),
        chain: edges,
      };
    if (path.endsWith("/classify"))
      data = {
        suggestions: [
          {
            category_id: "backend",
            path: "技术开发 / 后端",
            confidence: 0.9,
            reason: "依据已发布知识匹配",
          },
        ],
      };
    return r.fulfill({ json: data });
  });
});
test("knowledge graph supports scenario, backlinks, navigation and manual links", async ({
  page,
}) => {
  await page.goto("/#/graph?doc=doc%3Aone");
  await expect(page.getByRole("img", { name: "知识关系图谱" })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "选择知识：连接池故障排查" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "放大图谱", exact: true }).click();
  await page.getByRole("button", { name: "适应图谱", exact: true }).click();
  await page.getByRole("button", { name: "选择知识：事务回滚方案" }).click();
  await expect(page.locator(".graph-detail")).toContainText("来自");
  await page.getByLabel("知识链使用场景").selectOption("troubleshoot");
  await page.getByLabel("知识链深度").selectOption("2");
  await page.getByRole("button", { name: "建立明确关系", exact: true }).click();
  await page.getByLabel("目标文档 ID").fill("doc:two");
  const req = page.waitForRequest(
    (r) => r.url().endsWith("/graph/links") && r.method() === "POST",
  );
  await page.getByRole("button", { name: "保存知识关系", exact: true }).click();
  expect((await req).postDataJSON().source_id).toBe("doc:one");
  await expect(page.locator(".toast")).toContainText("知识关系已保存");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
test("cloud assistant offers grounded answer and navigable sources", async ({
  page,
}) => {
  await page.goto("/#/assistant");
  await page.getByLabel("知识问答问题").fill("连接池故障怎么排查？");
  await page.getByLabel("检索方式").selectOption("chain");
  await page.getByRole("button", { name: "开始分析" }).click();
  await expect(page.locator(".assistant-answer")).toContainText(
    "检查连接池状态",
  );
  await expect(page.locator(".assistant-sources")).toContainText(
    "[1] 连接池故障排查",
  );
  await expect(page.locator(".assistant-answer")).toContainText("知识链分析");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page
    .locator(".assistant-source")
    .first()
    .getByRole("link", { name: "查看知识链 →" })
    .click();
  await expect(
    page.getByRole("heading", { name: "知识链", exact: true }),
  ).toBeVisible();
});
test("unconfigured assistant clearly blocks model requests", async ({
  page,
}) => {
  await page.route("**/api/v1/assistant/status", (r) =>
    r.fulfill({
      json: { ready: false, enabled: false, key_configured: false },
    }),
  );
  await page.goto("/#/assistant");
  await expect(
    page.getByRole("heading", { name: "模型服务尚未启用" }),
  ).toBeVisible();
  await page.getByLabel("知识问答问题").fill("如何开发接口？");
  await expect(page.getByRole("button", { name: "开始分析" })).toBeDisabled();
});

test("Obsidian wiki links resolve documents and preserve code examples", async ({
  page,
}) => {
  await page.route("**/api/v1/graph*", (route) =>
    route.fulfill({
      json: {
        nodes: [
          { id: "doc:one", title: "连接池故障排查" },
          { id: "doc:two", title: "事务回滚方案" },
        ],
        edges: [],
        suggestions: [],
        categories,
      },
    }),
  );
  await page.route("**/api/v1/read", (route) =>
    route.fulfill({
      json: {
        id: "doc:one",
        title: "部署说明",
        category_id: "backend",
        content:
          "请先看 [[连接池故障排查|连接池排障]]，然后看 [[同名文档]]。\n\n```md\n[[事务回滚方案]]\n```",
        knowledge_version: 1,
        total_chars: 100,
        truncated: false,
      },
    }),
  );
  await page.goto("/#/documents/doc%3Aone");
  await expect(page.getByRole("link", { name: "连接池排障" })).toHaveAttribute(
    "href",
    "#/documents/doc%3Aone",
  );
  await expect(page.locator(".prose")).toContainText("[[同名文档]]");
  await expect(page.locator("pre")).toContainText("[[事务回滚方案]]");
});

test("unlinked documents stay independent and similarity is optional reading", async ({
  page,
}) => {
  await page.route("**/api/v1/graph*", (route) =>
    route.fulfill({
      json: {
        center: "doc:one",
        nodes: [nodes[0]],
        edges: [],
        suggestions: [
          { id: "doc:three", title: "部署连接池", reason: "关键词相似" },
        ],
        categories,
      },
    }),
  );
  await page.goto("/#/graph?doc=doc%3Aone");
  await expect(
    page.getByRole("heading", { name: "这篇知识可以独立阅读" }),
  ).toBeVisible();
  await expect(page.getByRole("img", { name: "知识关系图谱" })).toHaveCount(0);
  await expect(page.locator(".graph-suggestion")).toHaveCount(0);
  await page.getByRole("button", { name: "可能相关", exact: true }).click();
  await expect(page.locator(".graph-suggestion")).toContainText("部署连接池");
  await expect(page.getByRole("img", { name: "知识关系图谱" })).toHaveCount(0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("opening the graph menu loads every explicitly connected document", async ({
  page,
}) => {
  await page.goto("/#/graph");
  await expect(
    page.getByRole("heading", { name: "全库知识链", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".kb-graph-card")).toHaveCount(2);
  await expect(page.locator(".graph-detail")).toContainText("问题与解法");
  await expect(page.locator(".chain-all-note")).toContainText("2 篇知识");
  await expect(page.locator(".chain-all-note")).toContainText(
    "相似内容不会自动连入",
  );
});

test("empty global graph shows a useful empty state instead of loading forever", async ({
  page,
}) => {
  await page.route("**/api/v1/graph/all*", (route) =>
    route.fulfill({
      json: {
        center: "",
        nodes: [],
        edges: [],
        suggestions: [],
        categories: [],
        truncated: false,
      },
    }),
  );
  await page.goto("/#/graph");
  await expect(
    page.getByRole("heading", { name: "先找到一篇值得展开的知识" }),
  ).toBeVisible();
  await expect(page.getByText("正在加载全部知识链…")).toHaveCount(0);
});
