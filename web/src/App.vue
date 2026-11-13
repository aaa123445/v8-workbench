<script setup>
import {
  ref,
  watch,
  onMounted,
  onBeforeUnmount,
  defineAsyncComponent,
} from "vue";
import { useRoute } from "vue-router";
import router from "./router";
import { X, CircleAlert, CheckCircle2 } from "lucide-vue-next";
import { loadSession, hasAccess } from "./composables/session";
import {
  authVersion,
  refreshStats,
  stats,
  notice,
  serviceHealth,
} from "./composables/workspace";
import ConfirmDialog from "./components/ConfirmDialog.vue";
import KeyDialog from "./components/KeyDialog.vue";
const PublicLayout = defineAsyncComponent(
  () => import("./layouts/PublicLayout.vue"),
);
const WorkspaceLayout = defineAsyncComponent(
  () => import("./layouts/WorkspaceLayout.vue"),
);
const route = useRoute(),
  online = ref(false);
watch(
  () => route.fullPath,
  () => {
    document.title = `${route.meta.title || "TeamKB"} · TeamKB 团队知识库`;
  },
  { immediate: true },
);
watch(
  authVersion,
  () => {
    if (hasAccess.value) refreshStats().catch(() => {});
    else stats.value = null;
  },
  { immediate: true },
);
// Warm a route chunk as soon as the user points at or focuses its link.
// Imports are shared with Vue Router, and a failed preload remains retryable.
const preloading = new WeakSet();
function preloadRoute(event) {
  const link = event.target.closest?.("a[href]");
  if (!link || link.origin !== location.origin || !link.hash.startsWith("#/"))
    return;
  const target = router.resolve(link.hash.slice(1));
  for (const record of target.matched) {
    const loader = record.components?.default;
    if (typeof loader !== "function" || preloading.has(loader)) continue;
    preloading.add(loader);
    Promise.resolve()
      .then(loader)
      .catch(() => preloading.delete(loader));
  }
}
onBeforeUnmount(() => {
  document.removeEventListener("pointerover", preloadRoute);
  document.removeEventListener("focusin", preloadRoute);
  document.removeEventListener("touchstart", preloadRoute);
});
onMounted(async () => {
  document.addEventListener("pointerover", preloadRoute, { passive: true });
  document.addEventListener("focusin", preloadRoute);
  document.addEventListener("touchstart", preloadRoute, { passive: true });
  loadSession().catch(() => {});
  try {
    const response = await fetch("/health");
    online.value = response.ok;
    if (response.ok) serviceHealth.value = await response.json();
  } catch {
    online.value = false;
  }
});
</script>
<template>
  <component
    :is="route.meta.layout === 'public' ? PublicLayout : WorkspaceLayout"
    :online="online"
    ><RouterView v-slot="{ Component }"
      ><Transition name="page" :duration="{ enter: 120, leave: 0 }"
        ><div :key="route.path" class="route-page">
          <component
            :is="Component"
          /></div></Transition></RouterView></component
  ><KeyDialog /><ConfirmDialog /><Transition name="toast"
    ><div v-if="notice" class="toast" :class="notice.kind" role="status">
      <CircleAlert v-if="notice.kind === 'error'" :size="19" /><CheckCircle2
        v-else
        :size="19"
      /><span>{{ notice.message }}</span
      ><button class="icon-button" aria-label="关闭提示" @click="notice = null">
        <X :size="16" />
      </button></div
  ></Transition>
</template>
