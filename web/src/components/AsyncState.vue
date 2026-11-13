<script setup>
import { LoaderCircle, CircleAlert, SearchX } from "lucide-vue-next";
import { keyDialogOpen } from "../composables/workspace";
defineProps({
  loading: Boolean,
  variant: { type: String, default: "default" },
  error: String,
  empty: Boolean,
  title: { default: "暂无内容" },
  description: String,
});
defineEmits(["retry"]);
</script>
<template>
  <div
    v-if="loading || error || empty"
    :class="[
      'async-state',
      { 'skeleton-state': loading && variant === 'cards' },
    ]"
    :role="error ? 'alert' : 'status'"
  >
    <div
      v-if="loading && variant === 'cards'"
      class="skeleton-grid"
      aria-hidden="true"
    >
      <div v-for="i in 6" :key="i" class="skeleton-card">
        <span /><i /><i /><i /><small />
      </div>
    </div>
    <LoaderCircle
      v-if="loading && variant !== 'cards'"
      class="spin"
      :size="28"
    /><CircleAlert v-else-if="error" :size="28" /><SearchX
      v-else-if="!loading"
      :size="30"
    />
    <h3 :class="{ 'sr-only': loading && variant === 'cards' }">
      {{ loading ? "正在加载…" : error || title }}
    </h3>
    <p v-if="description && !loading && !error">{{ description }}</p>
    <div v-if="error" class="inline-actions">
      <button class="button" @click="$emit('retry')">重新加载</button
      ><button
        v-if="error.includes('Key')"
        class="button primary"
        @click="keyDialogOpen = true"
      >
        配置 Key
      </button>
    </div>
  </div>
  <slot v-else />
</template>
