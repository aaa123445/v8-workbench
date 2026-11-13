<script setup>
import { lockBodyScroll } from "../composables/scrollLock";
import { ref, watch, nextTick, onMounted, onBeforeUnmount } from "vue";
import { AlertTriangle, X } from "lucide-vue-next";
import { confirmation, resolveConfirmation } from "../composables/confirmation";
import { trapFocus } from "../composables/accessibility";
const root = ref(null);
let previous, releaseScroll;
watch(confirmation, async (value, previousValue) => {
  if (value) {
    if (!previousValue) {
      previous = document.activeElement;
      releaseScroll = lockBodyScroll();
    }
    await nextTick();
    root.value?.querySelector("[data-cancel]")?.focus();
  } else {
    releaseScroll?.();
    releaseScroll = null;
    await nextTick();
    previous?.focus();
  }
});
function key(e) {
  if (!confirmation.value) return;
  if (e.key === "Escape") {
    e.preventDefault();
    e.stopPropagation();
    resolveConfirmation(false);
  } else trapFocus(e, root.value);
}
onMounted(() => document.addEventListener("keydown", key));
onBeforeUnmount(() => {
  document.removeEventListener("keydown", key);
  releaseScroll?.();
  releaseScroll = null;
  if (confirmation.value) resolveConfirmation(false);
});
</script>
<template>
  <Teleport to="body"
    ><div
      v-if="confirmation"
      class="modal-backdrop confirm-backdrop"
      @click.self="resolveConfirmation(false)"
    >
      <section
        ref="root"
        class="modal confirm-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        aria-describedby="confirm-message"
      >
        <button
          class="icon-button modal-close"
          aria-label="关闭确认"
          @click="resolveConfirmation(false)"
        >
          <X :size="18" /></button
        ><span :class="['confirm-icon', { 'is-danger': confirmation.danger }]"
          ><AlertTriangle :size="23"
        /></span>
        <h2 id="confirm-title">{{ confirmation.title }}</h2>
        <p id="confirm-message">{{ confirmation.message }}</p>
        <div class="confirm-actions">
          <button
            data-cancel
            class="button"
            @click="resolveConfirmation(false)"
          >
            取消</button
          ><button
            :class="['button', confirmation.danger ? 'danger' : 'primary']"
            @click="resolveConfirmation(true)"
          >
            {{ confirmation.confirmLabel }}
          </button>
        </div>
      </section>
    </div></Teleport
  >
</template>
<style>
.modal-backdrop.confirm-backdrop {
  z-index: 180;
}
.confirm-dialog {
  max-width: 440px;
  padding: 28px;
}
.confirm-dialog h2 {
  font-size: 20px;
  margin: 20px 0 12px;
  letter-spacing: -0.025em;
}
.confirm-dialog > p {
  font-size: 14px;
  line-height: 1.85;
  color: #667085;
  white-space: pre-line;
}
.confirm-icon {
  display: grid;
  place-items: center;
  background: #eef2ff;
  color: #465fff;
  width: 48px;
  height: 48px;
  border-radius: 14px;
}
.confirm-icon.is-danger {
  background: #fff0ef;
  color: #d92d20;
}
.confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 28px;
}
.confirm-actions .danger {
  background: #d92d20;
  color: white;
  border-color: #d92d20;
}
.confirm-actions .danger:hover {
  background: #b42318;
}
</style>
