<script setup>
import { computed, ref, onBeforeUnmount } from "vue";
import { useRoute, useRouter } from "vue-router";
import { BookOpen, Download, ArrowRight, PlugZap } from "lucide-vue-next";
import MarkdownContent from "../components/MarkdownContent.vue";
import guide from "../../../docs/usage.md?raw";
const route = useRoute(),
  router = useRouter();
const sections = guide
  .split(/(?=^## )/m)
  .filter((part) => part.startsWith("## "))
  .map((part) => ({
    title: part.split("\n")[0].replace(/^## /, ""),
    content: part,
  }));
const index = computed(() => {
  const value = Number(route.query.section);
  return Number.isInteger(value)
    ? Math.max(0, Math.min(sections.length - 1, value))
    : 0;
});
const selected = computed(() => sections[index.value]);
const downloadUrl = URL.createObjectURL(
  new Blob([guide], { type: "text/markdown;charset=utf-8" }),
);
onBeforeUnmount(() => URL.revokeObjectURL(downloadUrl));
function select(i) {
  router.replace({ path: "/guide", query: { section: i } });
}
</script>
<template>
  <section class="guide-page">
    <div class="page-heading">
      <div>
        <div class="eyebrow section-eyebrow">GET CONNECTED, START BUILDING</div>
        <h1>使用说明</h1>
        <p>从账号入网到 Agent 接入，一份文档完成 MCP、Skill 和 CLI 的配置。</p>
      </div>
      <div class="inline-actions">
        <RouterLink to="/connect" class="button primary"
          ><PlugZap :size="16" />一键接入</RouterLink
        ><a
          :href="downloadUrl"
          download="v8-workbench-使用说明.md"
          class="button"
          ><Download :size="16" />下载完整文档</a
        >
      </div>
    </div>
    <div class="guide-layout">
      <nav class="guide-toc panel" aria-label="使用说明目录">
        <h2><BookOpen :size="18" />快速导航</h2>
        <button
          v-for="(section, i) in sections"
          :key="section.title"
          :class="{ active: index === i }"
          @click="select(i)"
        >
          {{ section.title }}</button><RouterLink
          to="/account"
          class="text-link"
          >管理我的 Key <ArrowRight :size="14"
        /></RouterLink>
      </nav>
      <article class="panel guide-body">
        <MarkdownContent :content="selected.content" />
        <div class="guide-pagination">
          <button v-if="index > 0" class="button" @click="select(index - 1)">
            ← 上一节</button
          ><button
            v-if="index < sections.length - 1"
            class="button"
            @click="select(index + 1)"
          >
            下一节 →
          </button>
        </div>
      </article>
    </div>
  </section>
</template>
