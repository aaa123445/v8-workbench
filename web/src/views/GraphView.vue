<script setup>
import { ref, computed, watch, onBeforeUnmount } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  Network,
  Search,
  ArrowRight,
  Plus,
  Trash2,
  ZoomIn,
  ZoomOut,
} from "lucide-vue-next";
import { api, post } from "../services/api";
import { notify } from "../composables/workspace";
import { currentUser, hasAccess } from "../composables/session";
import { useResource } from "../composables/useResource";
import "../styles/intelligence.css";
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
  category = ref(""),
  zoom = ref(1);
const { data: taxonomy } = useResource(() => api("/categories"));
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
const palette = [
  "#465fff",
  "#875bf7",
  "#12a389",
  "#df8c24",
  "#dc5c87",
  "#4579ca",
];
const nodeMap = computed(() =>
  Object.fromEntries(
    (graph.value?.nodes || []).map((n, i, all) => {
      const angle =
        ((i - 1) * Math.PI * 2) / Math.max(1, all.length - 1) - Math.PI / 2;
      const radius = all.length > 12 && i % 2 ? 155 : 245;
      return [
        n.id,
        {
          ...n,
          x: i === 0 ? 450 : 450 + Math.cos(angle) * radius,
          y: i === 0 ? 310 : 310 + Math.sin(angle) * radius,
          color:
            palette[
              Math.max(
                0,
                (graph.value.categories || []).findIndex(
                  (c) => c.id === n.category_id,
                ),
              ) % palette.length
            ],
        },
      ];
    }),
  ),
);
const selectedNode = computed(() => nodeMap.value[selected.value]);
const selectedEdges = computed(() =>
  (graph.value?.edges || []).filter(
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
  if (!id) return;
  graphController?.abort();
  const controller = new AbortController();
  graphController = controller;
  busy.value = true;
  error.value = "";
  try {
    graph.value = await api(
      "/graph?" +
        new URLSearchParams({
          doc_id: id,
          category_id: category.value,
          depth: depth.value,
          scenario: scenario.value,
        }),
      { signal: controller.signal },
    );
    selected.value = id;
  } catch (e) {
    if (e.name !== "AbortError") {
      error.value = e.message;
      graph.value = null;
    }
  } finally {
    if (graphController === controller) busy.value = false;
  }
}
watch([() => route.query.doc, depth, scenario, category], load, {
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
  <section class="intelligence-page">
    <div class="page-heading">
      <div>
        <div class="eyebrow section-eyebrow">CONNECTED KNOWLEDGE</div>
        <h1>知识链</h1>
        <p>从一篇知识出发，沿引用、前置知识与解决方案探索上下文。</p>
      </div>
      <RouterLink to="/assistant" class="button primary"
        >让智能体分析 <ArrowRight :size="15"
      /></RouterLink>
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
    <div v-if="graph" class="graph-workspace">
      <div class="panel graph-canvas-panel">
        <div class="graph-canvas-heading">
          <span
            ><Network :size="17" />{{ graph.nodes.length }} 篇知识 ·
            {{ graph.edges.length }} 条关系</span
          >
          <div>
            <button
              class="icon-button"
              aria-label="缩小图谱"
              @click="zoom = Math.max(0.6, zoom - 0.15)"
            >
              <ZoomOut :size="17" /></button
            ><button
              class="icon-button"
              aria-label="放大图谱"
              @click="zoom = Math.min(1.7, zoom + 0.15)"
            >
              <ZoomIn :size="17" />
            </button>
          </div>
        </div>
        <svg
          class="knowledge-graph"
          viewBox="0 0 900 620"
          aria-label="知识关系图谱"
          role="img"
        >
          <defs>
            <marker
              id="graph-arrow"
              markerWidth="8"
              markerHeight="8"
              refX="20"
              refY="4"
              orient="auto"
            >
              <path d="M0,0 L8,4 L0,8" fill="#b6c1d4" />
            </marker>
          </defs>
          <g
            :transform="`translate(${450 * (1 - zoom)} ${310 * (1 - zoom)}) scale(${zoom})`"
          >
            <line
              v-for="edge in graph.edges"
              :key="edge.id"
              :x1="nodeMap[edge.source_id]?.x"
              :y1="nodeMap[edge.source_id]?.y"
              :x2="nodeMap[edge.target_id]?.x"
              :y2="nodeMap[edge.target_id]?.y"
              :class="[
                'graph-edge',
                edge.origin,
                {
                  highlight:
                    edge.source_id === selected || edge.target_id === selected,
                },
              ]"
              marker-end="url(#graph-arrow)"
            >
              <title>
                {{ edge.label }} ·
                {{ edge.origin === "manual" ? "人工维护" : "正文引用" }}
              </title>
            </line>
            <g
              v-for="node in nodeMap"
              :key="node.id"
              class="graph-node"
              :transform="`translate(${node.x} ${node.y})`"
              role="button"
              tabindex="0"
              :aria-label="'选择知识：' + node.title"
              :aria-pressed="selected === node.id"
              @click="selected = node.id"
              @keydown.enter="selected = node.id"
              @keydown.space.prevent="selected = node.id"
            >
              <circle
                :r="node.id === graph.center ? 24 : 15"
                :fill="node.color"
                :class="{ selected: selected === node.id }"
              />
              <text y="42" text-anchor="middle">
                {{
                  node.title.length > 16
                    ? node.title.slice(0, 16) + "…"
                    : node.title
                }}
              </text>
              <title>{{ node.title }}</title>
            </g>
          </g>
        </svg>
        <div class="graph-legend">
          <span><i />人工维护关系</span><span><i class="dashed" />正文引用</span
          ><span>箭头表示源文档 → 关联目标</span>
        </div>
        <p v-if="graph.edges.length === 0" class="intelligence-muted">
          暂无已确认关系。可从推荐关联中选文档，人工建立知识链。
        </p>
        <p v-if="graph.truncated" class="intelligence-muted">
          当前显示最多 24 个节点，请切换中心继续探索。
        </p>
      </div>
      <aside class="graph-detail panel">
        <template v-if="selectedNode"
          ><span class="eyebrow">SELECTED KNOWLEDGE</span>
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
              v-if="selectedNode.id !== graph.center"
              class="button small"
              @click="center(selectedNode.id)"
            >
              以此为中心
            </button>
          </div>
          <h3>正向与反向关联</h3>
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
            该文档尚无引用或人工关系。
          </p></template
        >
      </aside>
    </div>
    <div v-else-if="!busy" class="panel graph-empty">
      <Network :size="44" />
      <h2>让零散的知识连接起来</h2>
      <p>
        先搜索并选择一篇知识。文档中的 [[标题]]、[[文档ID]]
        和站内文档链接会自动形成双向引用。
      </p>
      <RouterLink to="/library" class="button">浏览知识库</RouterLink>
    </div>
    <section
      v-if="graph?.reading_order?.length > 1"
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
    <div v-if="graph" class="graph-bottom">
      <section class="panel">
        <h2>推荐关联 <span class="badge">待确认</span></h2>
        <p class="intelligence-muted">
          基于关键词匹配推荐，不代表已确认关系或因果。
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
            ><button v-if="canWrite" class="text-link" @click="target = d.id">
              选择关联
            </button>
          </div>
        </div>
        <p v-if="!graph.suggestions.length" class="intelligence-muted">
          暂无足够相似的知识。
        </p>
      </section>
      <section v-if="canWrite" class="panel">
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
