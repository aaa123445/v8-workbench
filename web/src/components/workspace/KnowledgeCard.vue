<script setup>
import { FileText, ArrowUpRight, Clock3 } from "lucide-vue-next";
import { plainText, relativeDate, categoryTone } from "../../utils/format";
import { sourceLabel } from "../../composables/workspace";
defineProps({
  doc: { type: Object, required: true },
  category: { type: Object, default: null },
});
defineEmits(["tag"]);
</script>
<template>
  <article :class="['kb-card', 'tone-' + categoryTone(doc.category_id)]">
    <div class="knowledge-card-header">
      <span class="knowledge-doc-icon"><FileText :size="21" /></span
      ><span class="knowledge-category">{{ category?.name || "待分类" }}</span
      ><ArrowUpRight class="knowledge-open-icon" :size="17" />
    </div>
    <div class="knowledge-card-body">
      <h3>
        <RouterLink :to="{ name: 'document', params: { id: doc.id } }">{{
          doc.title
        }}</RouterLink>
      </h3>
      <p>
        {{
          plainText(doc.summary) ||
          "这份知识等待你的探索，打开查看完整内容与解决方案。"
        }}
      </p>
      <div class="kb-tags">
        <button
          v-for="tag in doc.tags.slice(0, 3)"
          :key="tag"
          class="badge"
          @click="$emit('tag', tag)"
        >
          {{ tag }}</button><span v-if="doc.tags.length > 3" class="more-tags"
          >+{{ doc.tags.length - 3 }}</span
        >
      </div>
    </div>
    <footer>
      <span><span class="source-dot" />{{ sourceLabel(doc.source) }}</span
      ><span><Clock3 :size="11" />{{ relativeDate(doc.updated_at) }}</span>
    </footer>
  </article>
</template>
