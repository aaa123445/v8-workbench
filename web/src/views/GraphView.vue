<script setup>
import {
  ref,
  computed,
  watch,
  onBeforeUnmount,
  defineAsyncComponent,
  h,
} from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  Network,
  Search,
  ArrowRight,
  Plus,
  Trash2,
  FileText,
  ChevronDown,
} from "lucide-vue-next";
import { api, post } from "../services/api";
import { notify, authVersion } from "../composables/workspace";
import { currentUser, hasAccess } from "../composables/session";
import { useResource } from "../composables/useResource";
import "../styles/intelligence.css";
const KnowledgeCanvas = defineAsyncComponent({
  loader: () => import("../components/graph/KnowledgeCanvas.vue"),
  delay: 0,
  timeout: 15000,
  loadingComponent: {
    render: () =>
      h(
        "div",
        { class: "chain-render-notice", role: "status" },
        "正在加载图谱组件…",
      ),
  },
  errorComponent: {
    render: () =>
      h("div", { class: "chain-render-notice", role: "alert" }, [
        h("p", "图谱资源加载失败，可先使用下方关系列表。"),
        h(
          "button",
          { class: "button", onClick: () => location.reload() },
          "刷新重试",
        ),
      ]),
  },
});
import "../styles/knowledge-chain.css";
const route = useRoute(),
  router = useRouter();
const query = ref(""),
  matches = ref([]),
  graph = ref(null),
  selected = ref(""),
  busy = ref(false),
  error = ref("");
const depth = ref(1),
  scenario = ref("explore"),
  category = ref("");
const showPossible = ref(false),
  showEditor = ref(false);
const { data: taxonomy } = useResource(() => api("/categories"));
const showingAll = computed(() => !route.query.doc);
const displayGraph = computed(() => graph.value);
const displayEdges = computed(() =>
  (graph.value?.edges || []).filter((e) =>
    ["manual", "reference"].includes(e.origin),
  ),
);
const canWrite = computed(
  () =>
    hasAccess.value &&
    (!currentUser.value ||
      ["writer", "admin"].includes(currentUser.value.role)),
);
const relation = ref("related"),
  target = ref(""),
  note = ref(""),
  saving = ref(false);
const kinds = {
  related: "相关知识",
  prerequisite: "前置知识",
  solution: "问题与解法",
  example: "应用示例",
  contrast: "对比方案",
};
const scenarios = {
  explore: "知识探索",
  troubleshoot: "排障溯源",
  develop: "开发实施",
  compare: "方案对比",
  learn: "学习路线",
};
const nodeMap = computed(() =>
  Object.fromEntries((graph.value?.nodes || []).map((n) => [n.id, n])),
);
const confirmedEdges = computed(() =>
  (graph.value?.edges || []).filter((e) =>
    ["manual", "reference"].includes(e.origin),
  ),
);
const hasChain = computed(() => confirmedEdges.value.length > 0);
const selectedNode = computed(() => nodeMap.value[selected.value]);
const selectedEdges = computed(() =>
  confirmedEdges.value.filter(
    (e) => e.source_id === selected.value || e.target_id === selected.value,
  ),
);
let searchController, graphController;
async function search() {
  searchController?.abort();
  searchController = new AbortController();
  try {
    const d = await post(
      "/search",
      { query: query.value.trim(), category_id: category.value, limit: 8 },
      { signal: searchController.signal },
    );
    matches.value = d.results || [];
  } catch (e) {
    if (e.name !== "AbortError") notify(e.message, "error");
  }
}
function center(id) {
  router.replace({ path: "/graph", query: { doc: id } });
}
async function load() {
  const id = String(route.query.doc || "");
  graphController?.abort();
  const controller = new AbortController();
  graphController = controller;
  busy.value = true;
  error.value = "";
  try {
    graph.value = await api(
      id
        ? "/graph?" +
            new URLSearchParams({
              doc_id: id,
              category_id: category.value,
              depth: depth.value,
              scenario: scenario.value,
            })
        : "/graph/all?" + new URLSearchParams({ category_id: category.value }),
      { signal: controller.signal },
    );
    selected.value = id || graph.value.center;
    matches.value = [];
  } catch (e) {
    if (e.name !== "AbortError") {
      error.value = e.message;
      graph.value = null;
    }
  } finally {
    if (graphController === controller) busy.value = false;
  }
}
watch([() => route.query.doc, depth, scenario, category, authVersion], load, {
  immediate: true,
});
async function save() {
  saving.value = true;
  try {
    await post("/graph/links", {
      source_id: graph.value.center,
      target_id: target.value,
      kind: relation.value,
      note: note.value,
    });
    target.value = "";
    note.value = "";
    notify("知识关系已保存");
    await load();
  } catch (e) {
    notify(e.message, "error");
  } finally {
    saving.value = false;
  }
}
async function remove(edge) {
  try {
    await api("/graph/links/" + encodeURIComponent(edge.id), {
      method: "DELETE",
    });
    await load();
    notify("知识关系已移除");
  } catch (e) {
    notify(e.message, "error");
  }
}
onBeforeUnmount(() => {
  searchController?.abort();
  graphController?.abort();
});
</script>
<template>
  <section class="intelligence-page chain-page">
    <div class="page-heading">
      <div>
        <div class="eyebrow section-eyebrow">KNOWLEDGE CONNECTIONS</div>
        <h1>知识链</h1>
        <p>在需要串联思路时，沿真实引用与明确关系展开阅读。</p>
      </div>
      <div class="inline-actions">
        <RouterLink v-if="!showingAll" to="/graph" class="button"
          >返回全库知识链</RouterLink
        ><RouterLink to="/library" class="button"
          ><FileText :size="15" />浏览知识库</RouterLink
        >
      </div>
    </div>
    <div class="panel graph-controls">
      <form @submit.prevent="search">
        <Search :size="17" /><input
          v-model="query"
          aria-label="查找知识链起点"
          placeholder="搜索一篇文档，作为知识链起点"
          required
          maxlength="300"
        /><button class="button primary">查找</button>
      </form>
      <select v-model="category" aria-label="图谱分类范围">
        <option value="">全部分类</option>
        <option
          v-for="c in taxonomy?.categories || []"
          :key="c.id"
          :value="c.id"
        >
          {{ c.path }}
        </option></select
      ><select v-model="scenario" aria-label="知识链使用场景">
        <option v-for="(label, id) in scenarios" :key="id" :value="id">
          {{ label }}
        </option></select
      ><select v-model="depth" aria-label="知识链深度">
        <option :value="1">一跳关联</option>
        <option :value="2">两跳关联</option>
      </select>
    </div>
    <div v-if="matches.length" class="panel graph-search-results">
      <button v-for="d in matches" :key="d.id" @click="center(d.id)">
        <span>{{ d.title }}</span><ArrowRight :size="14" />
      </button>
    </div>
    <p v-if="error" class="error-text" role="alert">{{ error }}</p>
    <p v-if="busy" class="intelligence-muted" role="status">
      正在整理知识关系…
    </p>
    <section
      v-if="showingAll && busy"
      class="panel chain-entrypoints"
      role="status"
    >
      <h2>正在加载全部知识链…</h2>
      <p class="intelligence-muted">只整理明确引用和人工确认关系。</p>
    </section>
    <section
      v-if="showingAll && error"
      class="panel chain-entrypoints"
      role="alert"
    >
      <h2>知识链加载失败</h2>
      <p>{{ error }}</p>
      <button class="button small" @click="load">重新加载</button>
    </section>
    <section
      v-if="showingAll && graph?.nodes?.length"
      class="panel chain-all-note"
    >
      <span class="chain-mini-label">ALL CONFIRMED CONNECTIONS</span
      ><strong>全库知识链</strong
      ><span
        >{{ graph.nodes.length }} 篇知识 ·
        {{ displayEdges.length }} 条明确关系</span
      ><small>只展示正文引用和人工确认关系，相似内容不会自动连入。</small>
    </section>
    <div v-if="displayGraph?.nodes?.length" class="graph-workspace">
      <div class="panel graph-canvas-panel">
        <div class="chain-canvas-top">
          <div>
            <span class="chain-mini-label">{{
              showingAll ? "GLOBAL GRAPH" : "LOCAL GRAPH"
            }}</span>
            <h2>
              {{
                showingAll
                  ? "全库知识链"
                  : graph.nodes.find((n) => n.id === graph.center)?.title
              }}
            </h2>
          </div>
          <span class="chain-count">{{ displayEdges.length }} 条明确关系</span>
        </div>
        <KnowledgeCanvas
          v-if="displayEdges.length"
          :key="showingAll ? 'global' : graph.center"
          :graph="displayGraph"
          :global-view="showingAll"
          :selected="selected || displayGraph.center"
          @select="selected = $event"
        />
        <details v-if="displayEdges.length" class="chain-accessible-list">
          <summary>查看关系列表（{{ displayEdges.length }} 条）</summary>
          <div v-for="edge in confirmedEdges" :key="edge.id">
            <RouterLink
              :to="'/documents/' + encodeURIComponent(edge.source_id)"
              >{{ nodeMap[edge.source_id]?.title }}</RouterLink><span
              >{{ edge.label }} →</span
            ><RouterLink
              :to="'/documents/' + encodeURIComponent(edge.target_id)"
              >{{ nodeMap[edge.target_id]?.title }}</RouterLink
            >
          </div>
        </details>
        <div v-if="!hasChain" class="chain-standalone">
          <span class="chain-single-icon"><FileText :size="30" /></span
          ><span class="chain-mini-label">STANDALONE KNOWLEDGE</span>
          <h2>这篇知识可以独立阅读</h2>
          <p>
            目前没有明确引用或人工确认的关系。没有关联也没关系，不需要为了形成图谱而连接。
          </p>
          <RouterLink
            :to="'/documents/' + encodeURIComponent(graph.center)"
            class="button primary"
            >阅读这篇知识 <ArrowRight :size="14" /></RouterLink
          ><button v-if="canWrite" class="text-link" @click="showEditor = true">
            有明确关系时，再建立关联
          </button>
        </div>
        <div v-if="hasChain" class="graph-legend">
          <span><i />人工确认</span><span><i class="dashed" />正文引用</span
          ><span>箭头表示引用或关系方向</span>
        </div>
        <p v-if="hasChain && graph.truncated" class="intelligence-muted">
          当前仅显示部分节点，请缩小分类范围或选择文档继续阅读。
        </p>
      </div>
      <aside class="graph-detail panel">
        <template v-if="selectedNode"
          ><span class="eyebrow">知识详情</span>
          <h2>{{ selectedNode.title }}</h2>
          <p class="intelligence-muted">
            {{
              graph.categories.find((c) => c.id === selectedNode.category_id)
                ?.path
            }}
            · v{{ selectedNode.knowledge_version }}
          </p>
          <div class="inline-actions">
            <RouterLink
              :to="'/documents/' + encodeURIComponent(selectedNode.id)"
              class="button small"
              >阅读原文</RouterLink
            ><button
              v-if="showingAll || selectedNode.id !== graph.center"
              class="button small"
              @click="center(selectedNode.id)"
            >
              以此为中心
            </button>
          </div>
          <h3>
            明确关联 <span class="badge">{{ selectedEdges.length }}</span>
          </h3>
          <div v-for="e in selectedEdges" :key="e.id" class="graph-relation">
            <small
              >{{ e.origin === "manual" ? "人工维护" : "正文引用" }} ·
              {{ e.source_id === selected ? "指向" : "来自" }} ·
              {{ e.label }}</small
            ><button
              class="text-link"
              @click="
                selected = e.source_id === selected ? e.target_id : e.source_id
              "
            >
              {{
                nodeMap[e.source_id === selected ? e.target_id : e.source_id]
                  ?.title
              }}
            </button>
            <p v-if="e.note">{{ e.note }}</p>
            <button
              v-if="e.origin === 'manual' && canWrite"
              class="icon-button"
              :aria-label="'删除关系 ' + e.label"
              @click="remove(e)"
            >
              <Trash2 :size="13" />
            </button>
          </div>
          <p v-if="!selectedEdges.length" class="intelligence-muted">
            没有明确关联，保留为独立知识。
          </p></template
        >
      </aside>
    </div>
    <div
      v-else-if="!displayGraph?.nodes?.length && !busy"
      class="panel graph-empty"
    >
      <span class="chain-empty-icon"><Network :size="36" /></span>
      <span class="chain-mini-label">FIND YOUR THREAD</span>
      <h2>先找到一篇值得展开的知识</h2>
      <p>
        搜索问题、方案或文档标题。有明确引用的知识会自然形成链路，独立文档保持独立。
      </p>
      <RouterLink to="/library" class="button">浏览知识库</RouterLink>
    </div>
    <section
      v-if="
        hasChain && scenario !== 'explore' && graph?.reading_order?.length > 1
      "
      class="panel graph-reading-order"
    >
      <h2>{{ scenarios[scenario] }} · 建议阅读顺序</h2>
      <p class="intelligence-muted">
        按已知关系整理的阅读建议，需结合具体版本核验。
      </p>
      <ol>
        <li v-for="item in graph.reading_order" :key="item.id">
          <RouterLink :to="'/documents/' + encodeURIComponent(item.id)">{{
            item.title
          }}</RouterLink>
        </li>
      </ol>
    </section>
    <div v-if="graph && !showingAll" class="chain-secondary-actions">
      <button
        class="button small"
        :aria-expanded="showPossible"
        @click="showPossible = !showPossible"
      >
        <Search :size="14" />可能相关 <ChevronDown :size="13" /></button
      ><button
        v-if="canWrite && !showingAll"
        class="button small"
        :aria-expanded="showEditor"
        @click="showEditor = !showEditor"
      >
        <Plus :size="14" />建立明确关系</button
      ><span>相似内容不会自动成为知识链</span>
    </div>
    <div
      v-if="graph && !showingAll && (showPossible || showEditor)"
      class="graph-bottom"
    >
      <section v-if="showPossible" class="panel">
        <h2>可能相关 <span class="badge">仅供参考</span></h2>
        <p class="intelligence-muted">
          仅按关键词检索，未连入图谱。请先阅读，确有关系时再手动确认。
        </p>
        <div
          v-for="d in graph.suggestions"
          :key="d.id"
          class="graph-suggestion"
        >
          <RouterLink :to="'/documents/' + encodeURIComponent(d.id)">{{
            d.title
          }}</RouterLink><small>{{ d.reason }}</small>
          <div class="inline-actions">
            <button class="text-link" @click="center(d.id)">探索</button
            ><button
              v-if="canWrite"
              class="text-link"
              @click="
                target = d.id;
                showEditor = true;
              "
            >
              选择关联
            </button>
          </div>
        </div>
        <p v-if="!graph.suggestions.length" class="intelligence-muted">
          暂无足够相似的知识。
        </p>
      </section>
      <section v-if="canWrite && showEditor" class="panel">
        <h2><Plus :size="17" />建立知识关系</h2>
        <p class="intelligence-muted">
          从当前中心文档指向目标；“前置知识”表示学习中心文档前应先读目标文档。
        </p>
        <form @submit.prevent="save">
          <label class="field"
            >目标文档 ID<input
              v-model="target"
              required
              maxlength="200"
              placeholder="从推荐关联选择，或粘贴文档 ID" /></label
          ><label class="field"
            >关系类型<select v-model="relation">
              <option v-for="(label, id) in kinds" :key="id" :value="id">
                {{ label }}
              </option>
            </select></label
          ><label class="field"
            >关联说明<input
              v-model="note"
              maxlength="1000"
              placeholder="说明关系和适用场景" /></label
          ><button class="button primary" :disabled="saving || !target">
            {{ saving ? "保存中…" : "保存知识关系" }}
          </button>
        </form>
      </section>
    </div>
  </section>
</template>
