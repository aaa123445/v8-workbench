<script setup>
import { lockBodyScroll } from "../composables/scrollLock";
import { ref, watch, nextTick, onBeforeUnmount } from "vue";
import { KeyRound, X, LoaderCircle } from "lucide-vue-next";
import { api, post } from "../services/api";
import { currentUser } from "../composables/session";
import {
  apiKey,
  saveKey,
  keyDialogOpen,
  notify,
} from "../composables/workspace";
const draft = ref(""),
  busy = ref(false),
  error = ref(""),
  input = ref(null),
  dialog = ref(null);
let returnFocus, releaseScroll;
watch(keyDialogOpen, async (open) => {
  if (open) {
    returnFocus = document.activeElement;
    draft.value = apiKey.value;
    error.value = "";
    await nextTick();
    input.value?.focus();
    releaseScroll ||= lockBodyScroll();
  } else {
    releaseScroll?.();
    releaseScroll = null;
    returnFocus?.focus();
  }
});
onBeforeUnmount(() => {
  releaseScroll?.();
  releaseScroll = null;
});
async function submit() {
  if (!draft.value.trim()) {
    error.value = "请输入 API Key";
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    await api("/stats", { key: draft.value.trim() });
    await post("/auth/logout", {}, { key: "" });
    currentUser.value = null;
    saveKey(draft.value.trim());
    keyDialogOpen.value = false;
    notify("API Key 验证通过，已连接工作台");
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
function trap(event) {
  if (event.key === "Escape" && !busy.value) keyDialogOpen.value = false;
  if (event.key !== "Tab") return;
  const elements = [
    ...dialog.value.querySelectorAll("button:not(:disabled), input, a[href]"),
  ];
  const first = elements[0],
    last = elements.at(-1);
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}
</script>
<template>
  <Teleport to="body"
    ><div
      v-if="keyDialogOpen"
      class="modal-backdrop"
      @click.self="!busy && (keyDialogOpen = false)"
    >
      <section
        ref="dialog"
        class="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="key-title"
        @keydown="trap"
      >
        <button
          class="icon-button modal-close"
          aria-label="关闭"
          :disabled="busy"
          @click="keyDialogOpen = false"
        >
          <X :size="20" />
        </button>
        <span class="feature-icon"><KeyRound /></span>
        <h2 id="key-title">连接你的工作空间</h2>
        <p class="muted">
          使用管理员或团队分配的 API Key，访问知识库与开发规范。
        </p>
        <form @submit.prevent="submit">
          <label class="field"
            >API Key<input
              ref="input"
              v-model="draft"
              type="password"
              placeholder="输入你的 API Key"
              autocomplete="off"
          /></label>
          <p v-if="error" class="error-text" role="alert">{{ error }}</p>
          <p class="hint">Key 仅保存在当前浏览器，请在可信设备上使用。</p>
          <button class="button primary wide" :disabled="busy">
            <LoaderCircle v-if="busy" class="spin" :size="16" />{{
              busy ? "验证中…" : "验证并连接"
            }}
          </button>
        </form>
        <button
          v-if="apiKey"
          class="text-button disconnect"
          :disabled="busy"
          @click="
            saveKey('');
            keyDialogOpen = false;
            notify('已清除当前浏览器的 Key');
          "
        >
          断开连接并清除 Key
        </button>
      </section>
    </div></Teleport
  >
</template>
