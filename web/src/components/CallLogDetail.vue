<script setup>
import { lockBodyScroll } from "../composables/scrollLock";
import { ref, onMounted, onBeforeUnmount, nextTick } from "vue";
import { X, Copy, Activity, Clock3 } from "lucide-vue-next";
import { api } from "../services/api";
import { useResource } from "../composables/useResource";
import { trapFocus } from "../composables/accessibility";
import { notify } from "../composables/workspace";
import {
  operations,
  clients,
  outcomes,
  formatTime,
  formatDuration,
  formatSnapshot,
} from "../utils/callLogs";
import AsyncState from "./AsyncState.vue";
const props = defineProps({ id: { type: Number, required: true } });
const emit = defineEmits(["close"]);
const tab = ref("response"),
  dialog = ref(null),
  closeButton = ref(null);
const { data, loading, error, reload } = useResource(
  () => api("/account/calls/" + props.id),
  [() => props.id],
);
let returnFocus, releaseScroll;
onMounted(async () => {
  returnFocus = document.activeElement;
  releaseScroll = lockBodyScroll();
  await nextTick();
  closeButton.value?.focus();
});
onBeforeUnmount(() => {
  releaseScroll?.();
  returnFocus?.focus();
});
function keyboard(event) {
  if (event.key === "Escape") {
    event.preventDefault();
    emit("close");
  } else trapFocus(event, dialog.value);
}
async function copy() {
  try {
    await navigator.clipboard.writeText(formatSnapshot(data.value[tab.value]));
    notify("已复制当前调用快照");
  } catch {
    notify("复制失败，请手动选择内容", "error");
  }
}
</script>
<template>
  <Teleport to="body"
    ><div class="modal-backdrop call-log-backdrop" @click.self="$emit('close')">
      <section
        ref="dialog"
        class="call-log-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="call-log-title"
        @keydown="keyboard"
      >
        <header class="call-log-dialog-header">
          <span class="feature-icon"><Activity :size="20" /></span>
          <div>
            <span class="eyebrow">CALL DETAILS · #{{ id }}</span>
            <h2 id="call-log-title">调用详情</h2>
          </div>
          <button
            ref="closeButton"
            class="icon-button"
            aria-label="关闭调用详情"
            @click="$emit('close')"
          >
            <X :size="20" />
          </button>
        </header>
        <AsyncState :loading="loading" :error="error" @retry="reload"
          ><template v-if="data"
            ><div class="call-detail-meta">
              <span
                ><strong>{{
                  operations[data.operation] || data.operation
                }}</strong
                ><span :class="['call-outcome', data.outcome]">{{
                  outcomes[data.outcome]
                }}</span></span
              ><span>{{ formatTime(data.ts) }}</span
              ><span
                ><Clock3 :size="13" />{{
                  formatDuration(data.duration_ms)
                }}</span
              ><span
                >{{ clients[data.client] || data.client }} · HTTP
                {{ data.status_code }}</span
              >
            </div>
            <div class="call-detail-route">
              <code>{{ data.method }} {{ data.path }}</code
              ><span>{{
                data.credential_kind === "session"
                  ? "当前账号的网页会话"
                  : `${data.credential_name || "API Key"} · ${data.key_prefix}`
              }}</span>
            </div>
            <div class="call-snapshot-toolbar">
              <div class="segmented">
                <button
                  :class="{ active: tab === 'request' }"
                  @click="tab = 'request'"
                >
                  请求参数</button
                ><button
                  :class="{ active: tab === 'response' }"
                  @click="tab = 'response'"
                >
                  返回结果
                </button>
              </div>
              <button class="button small" @click="copy">
                <Copy :size="14" />复制当前内容
              </button>
            </div>
            <p
              v-if="
                tab === 'request'
                  ? data.request_truncated
                  : data.response_truncated
              "
              class="call-truncated"
              role="status"
            >
              {{
                tab === "request" ? "请求参数" : "返回结果"
              }}较长，此处仅保留截断快照。
            </p>
            <pre
              class="call-snapshot"
              :aria-label="tab === 'request' ? '请求参数快照' : '返回结果快照'"
            ><code>{{ formatSnapshot(data[tab]) }}</code></pre>
            <p class="hint call-detail-hint">
              快照记录本次实际返回的内容；敏感字段会隐藏，读取长文时仅记录本次返回的分段。
            </p></template
          ></AsyncState
        >
      </section>
    </div></Teleport
  >
</template>
