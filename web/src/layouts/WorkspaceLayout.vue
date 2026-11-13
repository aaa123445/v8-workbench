<script setup>
import { lockBodyScroll } from "../composables/scrollLock";
// TailAdmin Vue AppSidebar / AppHeader composition, adapted under MIT.
import {
  ref,
  computed,
  watch,
  nextTick,
  onMounted,
  onBeforeUnmount,
} from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  Search,
  BookOpen,
  Plus,
  ChartNoAxesCombined,
  Settings2,
  ArrowUpRight,
  ChevronRight,
  KeyRound,
  Menu,
  X,
  UserRound,
  LogIn,
  LogOut,
  LifeBuoy,
  House,
  PanelLeftClose,
  PanelLeftOpen,
  Activity,
  FolderTree,
  Files,
  ShieldCheck,
  Layers,
  ChevronDown,
  Command,
  PlugZap,
} from "lucide-vue-next";
import {
  currentUser,
  sessionReady,
  isAdmin,
  logout,
  statusLabel,
} from "../composables/session";
import { apiKey, keyDialogOpen, notice, stats } from "../composables/workspace";
import { focusMain, trapFocus } from "../composables/accessibility";
import BrandMark from "../components/ui/BrandMark.vue";
import CommandPalette from "../components/workspace/CommandPalette.vue";
import "../styles/workspace.css";
import "../styles/knowledge.css";
import "../styles/studio.css";
const props = defineProps({ online: Boolean }),
  route = useRoute(),
  router = useRouter();
const mobileOpen = ref(false),
  collapsed = ref(localStorage.getItem("v8wb_sidebar_collapsed") === "true"),
  paletteOpen = ref(false),
  trigger = ref(null),
  sidebarEl = ref(null);
const groups = computed(() => [
  {
    label: "知识空间",
    items: [
      { to: "/library", label: "团队知识库", icon: BookOpen },
      { to: "/workspace", label: "知识检索", icon: Search },
      { to: "/rules", label: "团队规范", icon: ShieldCheck },
      { to: "/overview", label: "知识总览", icon: ChartNoAxesCombined },
    ],
  },
  {
    label: "内容协作",
    items: [
      { to: "/contributions", label: "我的贡献", icon: Files },
      { to: "/contribute", label: "经验沉淀", icon: Plus },
      ...(isAdmin.value
        ? [
            { to: "/review", label: "贡献审核", icon: Layers },
            { to: "/categories", label: "分类管理", icon: FolderTree },
          ]
        : []),
    ],
  },
  {
    label: "连接与管理",
    items: [
      { to: "/connect", label: "一键接入", icon: PlugZap },
      { to: "/account/logs", label: "我的调用日志", icon: Activity },
      { to: "/account", label: "个人中心 / 我的 Key", icon: UserRound },
      { to: "/guide", label: "使用说明", icon: LifeBuoy },
      ...(isAdmin.value
        ? [{ to: "/admin", label: "工作台管理", icon: Settings2 }]
        : []),
    ],
  },
]);
function selected(to) {
  return route.path === to || (to === "/library" && route.name === "document");
}
watch(
  () => route.fullPath,
  () => {
    mobileOpen.value = false;
    paletteOpen.value = false;
  },
);
watch(collapsed, (value) =>
  localStorage.setItem("v8wb_sidebar_collapsed", String(value)),
);
let releaseScroll;
watch(mobileOpen, async (value) => {
  if (value) releaseScroll ||= lockBodyScroll();
  else {
    releaseScroll?.();
    releaseScroll = null;
  }
  await nextTick();
  if (value) sidebarEl.value?.querySelector("a")?.focus();
  else if (trigger.value?.getClientRects().length) trigger.value.focus();
});
function resize() {
  if (window.innerWidth > 900) mobileOpen.value = false;
}
function key(event) {
  const dialog = document.querySelector('[aria-modal="true"]');
  if (
    dialog &&
    !dialog.classList.contains("sidebar") &&
    !dialog.classList.contains("command-dialog")
  )
    return;
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    mobileOpen.value = false;
    paletteOpen.value = !paletteOpen.value;
    return;
  }
  if (!mobileOpen.value) return;
  if (event.key === "Escape") {
    event.preventDefault();
    mobileOpen.value = false;
  } else trapFocus(event, sidebarEl.value);
}
onMounted(() => {
  window.addEventListener("resize", resize);
  window.addEventListener("keydown", key);
});
onBeforeUnmount(() => {
  window.removeEventListener("resize", resize);
  window.removeEventListener("keydown", key);
  releaseScroll?.();
  releaseScroll = null;
});
async function signOut() {
  try {
    await logout();
    router.push("/login");
  } catch (e) {
    notice.value = { message: e.message, kind: "error" };
  }
}
</script>
<template>
  <div class="workspace" :class="{ 'sidebar-collapsed': collapsed }">
    <a class="skip-link" href="#main" @click.prevent="focusMain"
      >跳转到主要内容</a
    >
    <div
      v-if="mobileOpen"
      class="sidebar-overlay"
      @click="mobileOpen = false"
    />
    <aside
      ref="sidebarEl"
      class="sidebar"
      :class="{ 'is-open': mobileOpen }"
      :role="mobileOpen ? 'dialog' : undefined"
      :aria-modal="mobileOpen || undefined"
      aria-label="工作台导航"
    >
      <div class="sidebar-header">
        <RouterLink to="/" class="brand" aria-label="TeamKB 官网"
          ><BrandMark :compact="collapsed" /></RouterLink
        ><button
          class="icon-button sidebar-mobile-close"
          aria-label="关闭导航"
          @click="mobileOpen = false"
        >
          <X :size="19" />
        </button>
      </div>
      <RouterLink
        to="/library"
        class="workspace-switch"
        :title="collapsed ? '团队工作空间' : undefined"
        ><span class="workspace-avatar"><Layers :size="18" /></span
        ><span
          ><strong>团队工作空间</strong><small>共享知识 · 连接经验</small></span
        ><ChevronDown :size="14"
      /></RouterLink>
      <div class="sidebar-body">
        <nav
          v-for="group in groups"
          :key="group.label"
          :aria-label="group.label"
        >
          <div class="nav-label">{{ group.label }}</div>
          <RouterLink
            v-for="item in group.items"
            :key="item.to"
            :to="item.to"
            :title="collapsed ? item.label : undefined"
            :aria-label="item.label"
            :class="{ selected: selected(item.to) }"
            ><component :is="item.icon" :size="18" /><span>{{
              item.label
            }}</span
            ><small v-if="item.to === '/library' && stats" class="nav-count">{{
              stats.documents
            }}</small></RouterLink
          >
        </nav>
        <div class="sidebar-note">
          <span class="sidebar-note-icon"><Command :size="19" /></span
          ><strong>把知识带进工作流</strong>
          <p>连接 MCP、Skill 或 CLI，让 Agent 复用团队经验。</p>
          <RouterLink to="/guide"
            >查看接入指南 <ArrowUpRight :size="14"
          /></RouterLink>
        </div>
      </div>
      <div class="sidebar-bottom">
        <RouterLink to="/" class="back-to-site" title="返回官网"
          ><House :size="16" /><span>返回官网</span><ArrowUpRight :size="14"
        /></RouterLink>
        <div class="service-status">
          <span :class="['status-dot', { online: props.online }]" /><span>{{
            props.online ? "知识服务已连接" : "服务连接异常"
          }}</span
          ><small>TeamKB</small>
        </div>
      </div>
    </aside>
    <div class="workspace-main" :inert="mobileOpen || undefined">
      <header class="topbar">
        <button
          ref="trigger"
          class="icon-button mobile-toggle"
          aria-label="打开导航"
          :aria-expanded="mobileOpen"
          @click="mobileOpen = !mobileOpen"
        >
          <Menu :size="21" /></button
        ><button
          class="icon-button desktop-toggle"
          :aria-label="collapsed ? '展开侧栏' : '收起侧栏'"
          @click="collapsed = !collapsed"
        >
          <PanelLeftOpen v-if="collapsed" :size="20" /><PanelLeftClose
            v-else
            :size="20"
          /></button
        ><span class="header-divider" />
        <div class="breadcrumb">
          <span>{{ route.meta.section }}</span><ChevronRight
            :size="14"
          /><strong>{{ route.meta.title }}</strong>
        </div>
        <div class="topbar-right">
          <button
            class="global-search-trigger"
            aria-label="打开全局搜索"
            @click="paletteOpen = true"
          >
            <Search :size="17" /><span>搜索知识或快速前往</span
            ><kbd>⌘ K</kbd></button
          ><RouterLink
            to="/guide"
            class="icon-button header-help"
            aria-label="接入指南"
            title="接入指南"
            ><LifeBuoy :size="20" /></RouterLink
          ><span class="header-divider account-divider" />
          <template v-if="currentUser"
            ><RouterLink to="/account" class="account-chip"
              ><span class="avatar-small">{{
                currentUser.display_name.slice(0, 1)
              }}</span
              ><span
                ><strong>{{ currentUser.display_name }}</strong
                ><small>{{ statusLabel(currentUser.status) }}</small></span
              ></RouterLink
            ><button class="icon-button" aria-label="退出登录" @click="signOut">
              <LogOut :size="18" /></button
          ></template>
          <template v-else
            ><RouterLink v-if="!apiKey" to="/login" class="button key-button"
              ><LogIn :size="16" />登录 / 注册</RouterLink
            ><button
              class="button key-button legacy-key-button"
              @click="keyDialogOpen = true"
            >
              <KeyRound :size="16" />{{
                apiKey ? "访问凭据" : "使用 API Key"
              }}</button
            ><span
              v-if="apiKey"
              class="avatar-small key-avatar"
              title="API Key 已连接"
              ><UserRound :size="18" /></span
          ></template>
        </div>
      </header>
      <main id="main" class="content" tabindex="-1">
        <div v-if="!sessionReady" class="async-state" role="status">
          正在恢复工作空间…
        </div>
        <slot v-else />
      </main>
      <footer class="page-footer">
        <span>TeamKB <i /> 团队的每一份经验，都值得被连接。</span
        ><a href="/docs" target="_blank" rel="noopener"
          >API 文档 <ArrowUpRight :size="13"
        /></a>
      </footer>
    </div>
    <CommandPalette :open="paletteOpen" @close="paletteOpen = false" />
  </div>
</template>
