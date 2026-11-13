import { createRouter, createWebHashHistory } from "vue-router";
const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: "/connect",
      component: () => import("./views/ConnectView.vue"),
      meta: { title: "一键接入", section: "连接与管理" },
    },
    {
      path: "/library",
      component: () => import("./views/LibraryView.vue"),
      meta: { title: "团队知识库", section: "工作空间" },
    },
    {
      path: "/contributions",
      component: () => import("./views/ContributionsView.vue"),
      meta: { title: "我的贡献", section: "工作空间" },
    },
    {
      path: "/review",
      component: () => import("./views/ContributionsView.vue"),
      meta: { title: "贡献审核", section: "管理" },
    },
    {
      path: "/categories",
      component: () => import("./views/CategoriesView.vue"),
      meta: { title: "分类管理", section: "管理" },
    },
    {
      path: "/",
      name: "home",
      component: () => import("./views/LandingView.vue"),
      meta: { title: "首页", section: "TeamKB", layout: "public" },
    },
    {
      path: "/login",
      component: () => import("./views/AuthView.vue"),
      meta: { title: "账号登录", section: "账号", layout: "public" },
    },
    {
      path: "/register",
      component: () => import("./views/AuthView.vue"),
      meta: { title: "注册入网", section: "账号", layout: "public" },
    },
    {
      path: "/account/logs",
      component: () => import("./views/CallLogsView.vue"),
      meta: { title: "我的调用日志", section: "账号" },
    },
    {
      path: "/account",
      component: () => import("./views/AccountView.vue"),
      meta: { title: "个人中心", section: "账号" },
    },
    {
      path: "/guide",
      component: () => import("./views/GuideView.vue"),
      meta: { title: "使用说明", section: "帮助" },
    },
    {
      path: "/workspace",
      alias: "/search",
      name: "search",
      component: () => import("./views/SearchView.vue"),
      meta: { title: "知识检索", section: "工作空间" },
    },
    {
      path: "/documents/:id",
      name: "document",
      component: () => import("./views/DocumentView.vue"),
      meta: { title: "文档阅读", section: "知识检索" },
    },
    {
      path: "/rules",
      component: () => import("./views/StandardsView.vue"),
      meta: { title: "团队规范", section: "工作空间" },
    },
    {
      path: "/contribute",
      component: () => import("./views/ContributeView.vue"),
      meta: { title: "经验沉淀", section: "工作空间" },
    },
    {
      path: "/overview",
      component: () => import("./views/OverviewView.vue"),
      meta: { title: "知识总览", section: "工作空间" },
    },
    {
      path: "/admin",
      component: () => import("./views/AdminView.vue"),
      meta: { title: "工作台管理", section: "设置" },
    },
    { path: "/:pathMatch(.*)*", redirect: "/" },
  ],
  scrollBehavior: () => ({ top: 0 }),
});

// Query-only transitions do not run route-level beforeEnter guards. Keep the
// legacy root search link working both on initial load and within the SPA.
router.beforeEach((to) =>
  to.name === "home" && to.query.q
    ? { name: "search", query: to.query, replace: true }
    : true,
);
export default router;
