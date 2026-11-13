<script setup>
import { ref } from "vue";
import { post } from "../services/api";
const props = defineProps({ title: String, content: String }),
  emit = defineEmits(["select"]);
const suggestions = ref([]),
  busy = ref(false),
  error = ref(""),
  checked = ref(false);
async function classify() {
  busy.value = true;
  error.value = "";
  try {
    const data = await post("/classify", {
      title: props.title || "",
      content: (props.content || "").slice(0, 10000),
    });
    suggestions.value = data.suggestions || [];
    checked.value = true;
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <div class="category-suggestion">
    <button
      type="button"
      class="button small"
      :disabled="busy || !(title?.trim() || content?.trim())"
      @click="classify"
    >
      {{ busy ? "正在识别…" : "智能推荐分类" }}</button><span class="hint"
      >参考已发布知识，选择后才应用。</span
    >
    <p v-if="error" class="error-text" role="alert">{{ error }}</p>
    <div
      v-for="c in suggestions"
      :key="c.category_id"
      class="category-suggestion-item"
    >
      <button
        type="button"
        class="text-link"
        @click="emit('select', c.category_id)"
      >
        {{ c.path }} · 采用此分类</button
      ><small
        >{{ c.reason }} · 匹配占比 {{ Math.round(c.confidence * 100) }}%</small
      >
    </div>
    <p v-if="checked && !suggestions.length" class="hint">
      暂无足够依据，请手动选择分类。
    </p>
  </div>
</template>
<style scoped>
.category-suggestion {
  margin: -3px 0 18px;
}
.category-suggestion > .hint {
  margin-left: 10px;
}
.category-suggestion-item {
  display: grid;
  gap: 5px;
  padding: 10px 0;
  border-bottom: 1px solid #eaecf0;
}
.category-suggestion-item small {
  color: #667085;
  font-size: 11px;
}
</style>
