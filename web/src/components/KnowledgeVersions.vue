<script setup>
import { lockBodyScroll } from "../composables/scrollLock";
import { ref, watch, nextTick, onBeforeUnmount } from "vue";
import {
  History,
  X,
  GitBranch,
  RotateCcw,
  LoaderCircle,
} from "lucide-vue-next";
import { api, post } from "../services/api";
import { isAdmin } from "../composables/session";
import { notify } from "../composables/workspace";
import { confirmAction } from "../composables/confirmation";
import { trapFocus } from "../composables/accessibility";
import MarkdownContent from "./MarkdownContent.vue";
const props = defineProps({ doc: Object }),
  emit = defineEmits(["restored"]),
  versions = ref([]),
  selected = ref(null),
  open = ref(false),
  error = ref(""),
  busy = ref(false),
  loading = ref(false),
  root = ref(null);
let previous,
  releaseScroll,
  sequence = 0;
watch(open, async (value) => {
  if (value) {
    previous = document.activeElement;
    releaseScroll = lockBodyScroll();
    await nextTick();
    root.value?.querySelector("[data-version-close]")?.focus();
  } else {
    sequence++;
    releaseScroll?.();
    releaseScroll = null;
    await nextTick();
    previous?.focus();
  }
});
async function load() {
  open.value = true;
  selected.value = null;
  error.value = "";
  loading.value = true;
  const current = ++sequence;
  try {
    const out = await api("/versions/" + encodeURIComponent(props.doc.id));
    if (current === sequence) versions.value = out.versions || [];
  } catch (e) {
    if (current === sequence) error.value = e.message;
  } finally {
    if (current === sequence) loading.value = false;
  }
}
async function view(v) {
  const current = ++sequence;
  loading.value = true;
  error.value = "";
  try {
    const out = await api(
      "/versions/" + encodeURIComponent(props.doc.id) + "/" + v.version,
    );
    if (current === sequence) selected.value = out;
  } catch (e) {
    if (current === sequence) error.value = e.message;
  } finally {
    if (current === sequence) loading.value = false;
  }
}
async function rollback() {
  if (
    !(await confirmAction({
      title: "恢复历史版本？",
      message: `将版本 ${selected.value.version} 恢复为新的当前版本，现有历史记录会完整保留。`,
      confirmLabel: "确认恢复",
    }))
  )
    return;
  busy.value = true;
  try {
    await post("/versions/" + encodeURIComponent(props.doc.id) + "/rollback", {
      version: selected.value.version,
      expected_version: props.doc.knowledge_version,
    });
    notify("已恢复为新版本");
    open.value = false;
    emit("restored");
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
function key(e) {
  if (e.key === "Escape") {
    e.preventDefault();
    open.value = false;
  } else trapFocus(e, root.value);
}
onBeforeUnmount(() => {
  sequence++;
  releaseScroll?.();
  releaseScroll = null;
});
</script>
<template>
  <div class="kb-versions">
    <div class="kb-actions">
      <RouterLink
        :to="{ path: '/contribute', query: { target: doc.id } }"
        class="button small"
        ><GitBranch :size="13" />建议更新</RouterLink
      ><button class="button small" @click="load">
        <History :size="13" />版本历史 · v{{ doc.knowledge_version || 1 }}
      </button>
    </div>
    <Teleport to="body"
      ><div v-if="open" class="version-backdrop" @click.self="open = false">
        <section
          ref="root"
          class="version-drawer"
          role="dialog"
          aria-modal="true"
          aria-label="文档版本历史"
          @keydown="key"
        >
          <header>
            <div>
              <span class="eyebrow">KNOWLEDGE HISTORY</span>
              <h2>版本历史</h2>
              <p>{{ doc.title }}</p>
            </div>
            <button
              data-version-close
              class="icon-button"
              aria-label="关闭版本历史"
              @click="open = false"
            >
              <X :size="20" />
            </button>
          </header>
          <div class="version-drawer-body">
            <div class="version-list">
              <button
                v-for="v in versions"
                :key="v.version"
                :class="{ active: selected?.version === v.version }"
                @click="view(v)"
              >
                <span class="version-node" /><span
                  ><strong
                    >v{{ v.version }} ·
                    {{
                      new Date(v.created_at * 1000).toLocaleDateString()
                    }}</strong
                  ><small>{{
                    v.version === doc.knowledge_version
                      ? "当前版本"
                      : "历史版本"
                  }}</small></span
                >
              </button>
            </div>
            <p v-if="error" class="error-text" role="alert">{{ error }}</p>
            <div v-if="loading" class="async-state" role="status">
              <LoaderCircle class="spin" :size="24" />正在加载版本…
            </div>
            <template v-else-if="selected"
              ><div class="version-meta">
                版本 {{ selected.version }} · {{ selected.actor }}
              </div>
              <MarkdownContent :content="selected.content"
            /></template>
            <div v-else class="version-hint">
              <History :size="32" />
              <h3>每一次改进，都有迹可循</h3>
              <p>选择一个版本查看完整内容。</p>
            </div>
          </div>
          <footer v-if="selected">
            <span>历史内容以只读快照保存</span
            ><button
              v-if="isAdmin && selected.version !== doc.knowledge_version"
              class="button primary"
              :disabled="busy"
              @click="rollback"
            >
              <RotateCcw :size="15" />恢复此版本</button
            ><button v-else class="button" @click="open = false">完成</button>
          </footer>
        </section>
      </div></Teleport
    >
  </div>
</template>
<style>
.version-backdrop {
  position: fixed;
  inset: 0;
  z-index: 130;
  background: #10182866;
  backdrop-filter: blur(3px);
}
.version-drawer {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 720px;
  max-width: 100%;
  background: #fff;
  box-shadow: -15px 0 60px #10182820;
  display: flex;
  flex-direction: column;
  color: #344054;
}
.version-drawer > header {
  padding: 28px 30px;
  border-bottom: 1px solid #eaecf0;
  display: flex;
  align-items: flex-start;
  gap: 15px;
}
.version-drawer > header > div {
  flex: 1;
  min-width: 0;
}
.version-drawer > header .eyebrow {
  font-size: 9px;
  color: #98a2b3;
}
.version-drawer h2 {
  font-size: 23px;
  margin: 9px 0;
}
.version-drawer header p {
  font-size: 12px;
  color: #98a2b3;
  margin: 0;
  overflow-wrap: anywhere;
}
.version-drawer-body {
  flex: 1;
  overflow: auto;
  padding: 24px 30px;
}
.version-list {
  display: flex;
  flex-wrap: wrap;
  gap: 9px;
  margin-bottom: 25px;
}
.version-list button {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 11px 13px;
  border: 1px solid #e4e7ec;
  border-radius: 8px;
  text-align: left;
}
.version-list button.active {
  border-color: #a4bcfd;
  background: #f5f7ff;
}
.version-list strong {
  display: block;
  font-size: 12px;
  color: #475467;
  font-weight: 500;
}
.version-list small {
  font-size: 10px;
  color: #98a2b3;
  display: block;
  margin-top: 5px;
}
.version-node {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #bccafa;
  border: 2px solid #eef2ff;
}
.version-meta {
  font-size: 11px;
  color: #98a2b3;
  margin: 0 0 25px;
  padding-bottom: 15px;
  border-bottom: 1px solid #eaecf0;
}
.version-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  min-height: 300px;
  color: #bccafa;
  text-align: center;
}
.version-hint h3 {
  font-size: 16px;
  color: #667085;
  margin: 22px 0 10px;
}
.version-hint p {
  font-size: 12px;
  color: #98a2b3;
}
.version-drawer > footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 15px;
  border-top: 1px solid #eaecf0;
  padding: 18px 30px;
  font-size: 11px;
  color: #98a2b3;
}
.version-drawer .button.primary {
  background: #465fff;
  border-color: #465fff;
}
@media (max-width: 600px) {
  .version-drawer > header,
  .version-drawer-body {
    padding: 22px;
  }
  .version-drawer > footer {
    padding: 18px 22px;
  }
  .version-drawer > footer > span {
    font-size: 10px;
  }
}
</style>
