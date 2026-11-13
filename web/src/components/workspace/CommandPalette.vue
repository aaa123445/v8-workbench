<script setup>
import { lockBodyScroll } from "../../composables/scrollLock";
import { ref, watch, nextTick, onBeforeUnmount } from "vue";
import { useRouter } from "vue-router";
import {
  Search,
  ArrowUpRight,
  FileText,
  LoaderCircle,
  CornerDownLeft,
  X,
  BookOpen,
  Plus,
  Activity,
  PlugZap,
} from "lucide-vue-next";
import { post } from "../../services/api";
import { hasAccess } from "../../composables/session";
import { authVersion } from "../../composables/workspace";
import { trapFocus } from "../../composables/accessibility";
const props = defineProps({ open: Boolean }),
  emit = defineEmits(["close"]),
  router = useRouter();
const root = ref(null),
  input = ref(null),
  query = ref(""),
  results = ref([]),
  busy = ref(false),
  error = ref(""),
  active = ref(0);
const shortcuts = [
  { title: "一键接入本地 Agent", path: "/connect", icon: PlugZap },
  { title: "浏览团队知识库", path: "/library", icon: BookOpen },
  { title: "贡献一份新知识", path: "/contribute", icon: Plus },
  { title: "我的调用日志", path: "/account/logs", icon: Activity },
];
let timer, controller, previous, releaseScroll;
watch(
  () => props.open,
  async (open) => {
    if (open) {
      previous = document.activeElement;
      releaseScroll = lockBodyScroll();
      query.value = "";
      results.value = [];
      error.value = "";
      active.value = 0;
      await nextTick();
      input.value?.focus();
    } else {
      clearTimeout(timer);
      controller?.abort();
      releaseScroll?.();
      releaseScroll = null;
      await nextTick();
      previous?.focus();
    }
  },
);
watch([query, authVersion], () => {
  clearTimeout(timer);
  controller?.abort();
  results.value = [];
  error.value = "";
  active.value = 0;
  busy.value = false;
  if (!props.open || query.value.trim().length < 1) return;
  if (!hasAccess.value) {
    error.value = "登录或连接 API Key 后，即可检索团队知识。";
    return;
  }
  busy.value = true;
  controller = new AbortController();
  const current = controller;
  timer = setTimeout(async () => {
    try {
      const out = await post(
        "/search",
        { query: query.value.trim(), limit: 6 },
        { signal: current.signal },
      );
      if (current === controller) results.value = out.results || [];
    } catch (e) {
      if (e.name !== "AbortError" && current === controller)
        error.value = e.message;
    } finally {
      if (current === controller) busy.value = false;
    }
  }, 260);
});
function go(item) {
  emit("close");
  router.push(
    item.id ? { name: "document", params: { id: item.id } } : item.path,
  );
}
function key(e) {
  const items = query.value.trim() ? results.value : shortcuts;
  if (e.key === "Escape") {
    e.preventDefault();
    emit("close");
  } else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault();
    active.value =
      (active.value + (e.key === "ArrowDown" ? 1 : -1) + items.length) %
      Math.max(items.length, 1);
    root.value
      ?.querySelectorAll("[data-command]")
      [active.value]?.scrollIntoView({ block: "nearest" });
  } else if (e.key === "Enter") {
    e.preventDefault();
    if (items[active.value]) go(items[active.value]);
  } else trapFocus(e, root.value);
}
onBeforeUnmount(() => {
  clearTimeout(timer);
  controller?.abort();
  releaseScroll?.();
  releaseScroll = null;
});
</script>
<template>
  <Teleport to="body"
    ><div v-if="open" class="command-backdrop" @click.self="$emit('close')">
      <section
        ref="root"
        class="command-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="全局知识搜索"
        @keydown="key"
      >
        <div class="command-input">
          <Search :size="22" /><input
            ref="input"
            v-model="query"
            aria-label="全局搜索关键词"
            placeholder="搜索知识，或快速前往…"
            autocomplete="off"
          /><LoaderCircle v-if="busy" class="spin" :size="18" /><button
            class="icon-button"
            aria-label="关闭全局搜索"
            @click="$emit('close')"
          >
            <X :size="18" />
          </button>
        </div>
        <div class="command-body">
          <p class="command-label">
            {{ query.trim() ? "知识搜索结果" : "快速前往" }}
          </p>
          <p v-if="error" class="command-empty" role="alert">{{ error }}</p>
          <template v-else-if="!query.trim()"
            ><button
              v-for="(item, i) in shortcuts"
              :key="item.path"
              data-command
              :class="['command-result', { active: active === i }]"
              @mouseenter="active = i"
              @click="go(item)"
            >
              <component :is="item.icon" :size="19" /><span>{{
                item.title
              }}</span
              ><ArrowUpRight :size="15" /></button></template
          ><template v-else
            ><button
              v-for="(item, i) in results"
              :key="item.id"
              data-command
              :class="['command-result', { active: active === i }]"
              @mouseenter="active = i"
              @click="go(item)"
            >
              <FileText :size="19" /><span
                ><strong>{{ item.title }}</strong
                ><small>{{ item.path || "团队知识" }}</small></span
              ><CornerDownLeft :size="15" />
            </button>
            <p v-if="!busy && !results.length" class="command-empty">
              没有找到相关知识，试试更短的关键词。
            </p>
            <p
              v-if="busy && !results.length"
              class="command-empty"
              role="status"
            >
              正在检索团队知识…
            </p></template
          >
        </div>
        <footer>
          <span><kbd>↑</kbd><kbd>↓</kbd>选择 <kbd>↵</kbd>打开</span
          ><span><kbd>esc</kbd>关闭</span>
        </footer>
      </section>
    </div></Teleport
  >
</template>
<style>
.command-backdrop {
  position: fixed;
  inset: 0;
  z-index: 150;
  background: #10182866;
  backdrop-filter: blur(5px);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 14vh 20px 30px;
}
.command-dialog {
  width: 620px;
  max-width: 100%;
  background: white;
  border: 1px solid #e4e7ec;
  border-radius: 18px;
  box-shadow: 0 30px 100px #10182840;
  overflow: hidden;
  color: #344054;
}
.command-input {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 20px;
  border-bottom: 1px solid #eaecf0;
  color: #98a2b3;
}
.command-input input {
  width: 100%;
  border: 0;
  box-shadow: none !important;
  font-size: 16px;
  padding: 5px 0;
  outline: none !important;
}
.command-body {
  padding: 12px;
  max-height: 55vh;
  overflow: auto;
}
.command-label {
  font-size: 11px;
  letter-spacing: 0.04em;
  color: #98a2b3;
  margin: 6px 10px 10px;
}
.command-result {
  display: flex;
  align-items: center;
  width: 100%;
  text-align: left;
  gap: 14px;
  padding: 13px 12px;
  border-radius: 9px;
  color: #667085;
}
.command-result > span {
  flex: 1;
  min-width: 0;
  color: #344054;
  font-size: 14px;
}
.command-result strong {
  display: block;
  font-weight: 550;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.command-result small {
  display: block;
  font-size: 12px;
  color: #98a2b3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-top: 5px;
}
.command-result.active {
  background: #f2f4ff;
  color: #465fff;
}
.command-empty {
  padding: 25px 16px;
  color: #667085;
  font-size: 14px;
}
.command-dialog footer {
  display: flex;
  justify-content: space-between;
  padding: 12px 20px;
  border-top: 1px solid #eaecf0;
  font-size: 11px;
  color: #98a2b3;
  background: #fcfcfd;
}
.command-dialog kbd {
  display: inline-block;
  border: 1px solid #e4e7ec;
  background: white;
  border-radius: 4px;
  padding: 1px 4px;
  font-family: inherit;
  margin: 0 3px;
}
@media (max-width: 600px) {
  .command-backdrop {
    padding-top: 70px;
  }
  .command-input {
    padding: 16px;
  }
  .command-input input {
    font-size: 15px;
  }
}
</style>
