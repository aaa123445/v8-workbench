<script setup>
import { ref, nextTick } from "vue";
import {
  Bold,
  Italic,
  Heading2,
  List,
  Code2,
  Link,
  Quote,
  Columns2,
  Eye,
  Pencil,
  FilePlus2,
} from "lucide-vue-next";
import MarkdownContent from "../MarkdownContent.vue";
const props = defineProps({ modelValue: { type: String, default: "" } }),
  emit = defineEmits(["update:modelValue", "template"]),
  mode = ref("edit"),
  textarea = ref(null);
function insert(before, after = "", placeholder = "内容") {
  const el = textarea.value;
  if (!el) return;
  const start = el.selectionStart,
    end = el.selectionEnd,
    selection = props.modelValue.slice(start, end) || placeholder;
  emit(
    "update:modelValue",
    props.modelValue.slice(0, start) +
      before +
      selection +
      after +
      props.modelValue.slice(end),
  );
  nextTick(() => {
    el.focus();
    el.setSelectionRange(
      start + before.length,
      start + before.length + selection.length,
    );
  });
}
function shortcut(e) {
  if (!(e.metaKey || e.ctrlKey)) return;
  if (e.key.toLowerCase() === "b") {
    e.preventDefault();
    insert("**", "**", "加粗文字");
  } else if (e.key.toLowerCase() === "i") {
    e.preventDefault();
    insert("*", "*", "斜体文字");
  }
}
</script>
<template>
  <div class="markdown-editor">
    <div class="markdown-editor-top">
      <div class="editor-modes" aria-label="编辑器显示方式">
        <button
          type="button"
          :class="{ active: mode === 'edit' }"
          :aria-pressed="mode === 'edit'"
          @click="mode = 'edit'"
        >
          <Pencil :size="13" />编辑</button
        ><button
          type="button"
          :class="{ active: mode === 'preview' }"
          :aria-pressed="mode === 'preview'"
          @click="mode = 'preview'"
        >
          <Eye :size="13" />预览</button
        ><button
          type="button"
          class="split-editor-button"
          :class="{ active: mode === 'split' }"
          :aria-pressed="mode === 'split'"
          @click="mode = 'split'"
        >
          <Columns2 :size="13" />分屏
        </button>
      </div>
      <button
        type="button"
        class="text-link template-button"
        @click="$emit('template')"
      >
        <FilePlus2 :size="13" />使用经验模板
      </button>
    </div>
    <div
      v-if="mode !== 'preview'"
      class="markdown-toolbar"
      aria-label="Markdown 格式工具"
    >
      <button
        type="button"
        aria-label="插入标题"
        title="二级标题"
        @click="insert('\n## ', '\n', '章节标题')"
      >
        <Heading2 :size="17" /></button
      ><button
        type="button"
        aria-label="加粗文字"
        title="加粗 Ctrl+B"
        @click="insert('**', '**', '加粗文字')"
      >
        <Bold :size="16" /></button
      ><button
        type="button"
        aria-label="斜体文字"
        title="斜体 Ctrl+I"
        @click="insert('*', '*', '斜体文字')"
      >
        <Italic :size="16" /></button
      ><i /><button
        type="button"
        aria-label="插入列表"
        @click="insert('\n- ', '\n', '列表项')"
      >
        <List :size="17" /></button
      ><button
        type="button"
        aria-label="插入引用"
        @click="insert('\n> ', '\n', '引用内容')"
      >
        <Quote :size="16" /></button
      ><button
        type="button"
        aria-label="插入代码块"
        @click="insert('\n```\n', '\n```\n', '代码')"
      >
        <Code2 :size="18" /></button
      ><button
        type="button"
        aria-label="插入链接"
        @click="insert('[', '](https://example.com)', '链接文字')"
      >
        <Link :size="15" /></button
      ><span>Markdown</span>
    </div>
    <div :class="['markdown-editor-body', { 'is-split': mode === 'split' }]">
      <textarea
        v-if="mode !== 'preview'"
        id="knowledge-content"
        ref="textarea"
        :value="modelValue"
        aria-label="知识正文"
        minlength="20"
        maxlength="200000"
        rows="14"
        :placeholder="'从一个真实的问题开始，写下你的解决过程…\n\n## 问题与背景\n## 解决方案\n## 验证结果\n## 适用范围'"
        @input="$emit('update:modelValue', $event.target.value)"
        @keydown="shortcut"
      />
      <div v-if="mode !== 'edit'" class="editor-preview">
        <MarkdownContent
          :content="modelValue || '开始记录，让经验成为团队共同的答案。'"
        />
      </div>
    </div>
    <div class="markdown-editor-footer">
      <span>{{ modelValue.length.toLocaleString() }} 字符</span
      ><span>支持 Markdown · ⌘ / Ctrl + S 保存草稿</span>
    </div>
  </div>
</template>
