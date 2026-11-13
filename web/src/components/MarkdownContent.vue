<script setup>
import { computed, ref, watch, nextTick, useId } from "vue";
import { marked } from "marked";
import DOMPurify from "dompurify";
const props = defineProps({ content: { type: String, default: "" } }),
  emit = defineEmits(["headings"]),
  root = ref(null),
  scope = useId();
const rendered = computed(() => {
  const safe = DOMPurify.sanitize(
    marked.parse(props.content, { gfm: true, breaks: true }),
    {
      FORBID_TAGS: ["style", "form", "input", "button"],
      FORBID_ATTR: ["style"],
    },
  );
  const doc = new DOMParser().parseFromString(safe, "text/html");
  const headings = [];
  doc.querySelectorAll("h1,h2,h3,h4").forEach((node, i) => {
    node.id = `kb-${scope}-${i}`;
    node.tabIndex = -1;
    headings.push({
      id: node.id,
      text: node.textContent,
      level: Number(node.tagName[1]),
    });
  });
  return { html: doc.body.innerHTML, headings };
});
watch(
  rendered,
  async (value) => {
    emit("headings", value.headings);
    await nextTick();
    root.value?.querySelectorAll("pre").forEach((pre) => {
      pre.querySelector("button[data-code-copy]")?.remove();
      pre.classList.add("code-block");
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.codeCopy = "true";
      button.className = "code-copy";
      button.textContent = "复制";
      button.setAttribute("aria-label", "复制代码块");
      pre.append(button);
    });
  },
  { immediate: true, flush: "post" },
);
async function copyCode(event) {
  const button = event.target.closest("button[data-code-copy]");
  if (!button || !root.value?.contains(button)) return;
  const code = button.closest("pre")?.querySelector("code");
  if (!code) return;
  try {
    await navigator.clipboard.writeText(code.textContent);
    button.textContent = "已复制";
    setTimeout(() => {
      if (button.isConnected) button.textContent = "复制";
    }, 1800);
  } catch {
    button.textContent = "复制失败";
  }
}
</script>
<template>
  <div ref="root" class="prose" @click="copyCode" v-html="rendered.html" />
</template>
