<script setup>
import {
  ref,
  watch,
  onMounted,
  onBeforeUnmount,
  defineAsyncComponent,
} from "vue";
import { useRoute } from "vue-router";
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
onMounted(async () => {
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
      ><Transition name="page" mode="out-in"
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
