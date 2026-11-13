<script setup>
import { FileText, ArrowUpRight } from "lucide-vue-next";
import { sourceLabel } from "../composables/workspace";
defineProps({ doc: { type: Object, required: true } });
</script>
<template>
  <RouterLink
    :to="{ name: 'document', params: { id: doc.id } }"
    class="doc-card"
  >
    <div class="doc-card-top">
      <span class="file-icon"><FileText :size="19" /></span
      ><span class="eyebrow">{{ doc.domain || sourceLabel(doc.source) }}</span
      ><ArrowUpRight class="card-arrow" :size="18" />
    </div>
    <h3>{{ doc.title }}</h3>
    <p v-if="doc.snippet" class="snippet">{{ doc.snippet }}</p>
    <p v-else class="doc-path">
      {{ doc.path || "打开文档，查看完整内容与开发说明" }}
    </p>
    <div class="doc-card-footer">
      <span class="badge">{{ sourceLabel(doc.source) }}</span><span
        v-if="doc.version_hint"
        class="badge"
        >{{ doc.version_hint }}</span
      ><span v-if="doc.score !== undefined" class="match-score"
        >相关度 {{ Number(doc.score).toFixed(1) }}</span
      >
    </div>
  </RouterLink>
</template>
