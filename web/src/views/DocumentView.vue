<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  ArrowLeft,
  ExternalLink,
  Copy,
  FileText,
  LoaderCircle,
  Clock3,
  AlignLeft,
  ArrowUp,
  Check,
  BookOpen,
  Network,
} from "lucide-vue-next";
import { api, post } from "../services/api";
import { useResource } from "../composables/useResource";
import { sourceLabel, notify } from "../composables/workspace";
import AsyncState from "../components/AsyncState.vue";
import KnowledgeVersions from "../components/KnowledgeVersions.vue";
import MarkdownContent from "../components/MarkdownContent.vue";
const route = useRoute(),
  router = useRouter(),
  moreBusy = ref(false),
  toc = ref([]),
  active = ref(""),
  article = ref(null),
  progress = ref(0),
  copied = ref(false);
const emptyLinks = Object.freeze([]);
const {
  data: doc,
  loading,
  error,
  reload,
} = useResource(
  () => post("/read", { id: route.params.id, max_chars: 60000 }),
  [() => route.params.id],
);
const minutes = computed(() =>
  Math.max(1, Math.ceil((doc.value?.total_chars || 0) / 500)),
);
const { data: relations } = useResource(
  () => api("/graph?" + new URLSearchParams({ doc_id: route.params.id })),
  [() => route.params.id],
);
async function more() {
  moreBusy.value = true;
  try {
    const d = await post("/read", {
      id: doc.value.id,
      offset: doc.value.next_offset,
      max_chars: 60000,
    });
    if (d.knowledge_version !== doc.value.knowledge_version) {
      notify("文档已更新，请刷新后继续阅读。", "error");
      return;
    }
    doc.value = { ...d, content: doc.value.content + d.content };
  } catch (e) {
    notify(e.message, "error");
  } finally {
    moreBusy.value = false;
  }
}
async function copy() {
  try {
    await navigator.clipboard.writeText(doc.value.content);
    copied.value = true;
    setTimeout(() => (copied.value = false), 1800);
    notify(
      doc.value.truncated
        ? "已复制当前已加载的 Markdown，长文可继续加载后再复制"
        : "已复制文档 Markdown",
    );
  } catch {
    notify("复制失败，请检查浏览器剪贴板权限", "error");
  }
}
function back() {
  if (window.history.state.back) router.back();
  else router.push("/library");
}
function jump(id) {
  const node = document.getElementById(id);
  node?.scrollIntoView({
    behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
      ? "auto"
      : "smooth",
    block: "start",
  });
  node?.focus({ preventScroll: true });
  active.value = id;
}
let frame;
function scroll() {
  cancelAnimationFrame(frame);
  frame = requestAnimationFrame(() => {
    if (!article.value) return;
    const rect = article.value.getBoundingClientRect();
    const travel = Math.max(1, rect.height - window.innerHeight + 110);
    progress.value = Math.min(
      100,
      Math.max(0, Math.round(((100 - rect.top) / travel) * 100)),
    );
    let current = toc.value[0]?.id || "";
    for (const heading of toc.value) {
      const node = document.getElementById(heading.id);
      if (node?.getBoundingClientRect().top <= 155) current = heading.id;
    }
    active.value = current;
  });
}
function headings(value) {
  toc.value = value;
  nextTick(scroll);
}
onMounted(() => window.addEventListener("scroll", scroll, { passive: true }));
onBeforeUnmount(() => {
  window.removeEventListener("scroll", scroll);
  cancelAnimationFrame(frame);
});
</script>
<template>
  <section class="document-page">
    <div class="reader-topline">
      <button class="text-link back-link" @click="back">
        <ArrowLeft :size="16" />返回上一页</button
      ><span>团队知识 / 文档阅读</span>
    </div>
    <AsyncState :loading="loading" :error="error" @retry="reload"
      ><div v-if="doc" class="document-layout">
        <article ref="article" class="reader">
          <header class="reader-header">
            <div class="eyebrow">
              <FileText :size="14" />{{
                doc.category_path || doc.domain || "知识文档"
              }}
            </div>
            <h1>{{ doc.title }}</h1>
            <p class="doc-path">{{ doc.path }}</p>
            <div class="reader-meta">
              <span class="badge green">{{
                sourceLabel(doc.source)
              }}</span><span v-if="doc.version_hint" class="badge"
                >适用 {{ doc.version_hint }}</span
              ><span class="muted"
                ><Clock3 :size="12" />约 {{ minutes }} 分钟</span
              ><span class="muted"
                >{{ doc.total_chars.toLocaleString() }} 字</span
              >
            </div>
            <div class="reader-tools">
              <KnowledgeVersions :doc="doc" @restored="reload" /><span
                class="spacer"
              /><button class="button small" @click="copy">
                <Check v-if="copied" :size="14" /><Copy v-else :size="14" />{{
                  copied ? "已复制" : "复制 Markdown"
                }}</button
              ><a
                v-if="/^https?:\/\//.test(doc.url)"
                :href="doc.url"
                target="_blank"
                rel="noopener noreferrer"
                class="button small"
                >查看原文<ExternalLink :size="13"
              /></a>
              <RouterLink
                :to="{ path: '/graph', query: { doc: doc.id } }"
                class="button small"
                ><Network :size="14" />知识链</RouterLink
              >
            </div>
          </header>
          <MarkdownContent
            :content="doc.content"
            :wiki-links="relations?.nodes || emptyLinks"
            @headings="headings"
          />
          <div v-if="doc.truncated" class="reader-more">
            <p>还有更多内容，继续阅读完整方案。</p>
            <button class="button" :disabled="moreBusy" @click="more">
              <LoaderCircle
                v-if="moreBusy"
                class="spin"
                :size="16"
              />加载后续内容
            </button>
          </div>
          <footer class="reader-ending">
            <span>感谢团队的每一次分享</span
            ><RouterLink
              :to="{ path: '/contribute', query: { target: doc.id } }"
              >有更好的方案？建议更新 <ArrowUp :size="13"
            /></RouterLink>
          </footer>
        </article>
        <aside class="reading-sidebar">
          <div
            v-if="relations?.edges?.length"
            class="reading-toc"
            style="margin-bottom: 18px"
          >
            <h2><Network :size="15" />关联与反向引用</h2>
            <nav aria-label="关联知识">
              <RouterLink
                v-for="n in (relations?.nodes || []).filter(
                  (n) => n.id !== doc.id,
                )"
                :key="n.id"
                :to="'/documents/' + encodeURIComponent(n.id)"
                class="text-link"
                style="
                  display: block;
                  padding: 8px 0;
                  font-size: 12px;
                  line-height: 1.7;
                "
                >{{ n.title }}</RouterLink
              >
            </nav>
            <RouterLink
              :to="{ path: '/graph', query: { doc: doc.id } }"
              class="text-link"
              >展开知识链 →</RouterLink
            >
          </div>
          <div class="reading-toc">
            <h2><AlignLeft :size="15" />本页目录</h2>
            <nav aria-label="文档目录">
              <button
                v-for="h in toc"
                :key="h.id"
                :style="{
                  paddingLeft: 12 + Math.max(0, h.level - 2) * 10 + 'px',
                }"
                :class="{ active: active === h.id }"
                @click="jump(h.id)"
              >
                {{ h.text }}
              </button>
              <p v-if="!toc.length">当前文档没有章节标题</p>
            </nav>
            <div class="reading-progress">
              <span
                >阅读进度 <strong>{{ progress }}%</strong></span
              >
              <div
                role="progressbar"
                aria-label="阅读进度"
                :aria-valuenow="progress"
                aria-valuemin="0"
                aria-valuemax="100"
              >
                <i :style="{ width: progress + '%' }" />
              </div>
            </div>
          </div>
          <div class="reading-note">
            <BookOpen :size="20" /><strong>让知识持续生长</strong>
            <p>发现新的解法或适用限制？提交更新建议，帮助下一位团队成员。</p>
            <RouterLink :to="{ path: '/contribute', query: { target: doc.id } }"
              >完善这份知识 →</RouterLink
            >
          </div>
        </aside>
      </div></AsyncState
    >
  </section>
</template>
