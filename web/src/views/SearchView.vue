<script setup>
import { ref, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  Search,
  ArrowRight,
  BookOpen,
  Layers,
  ArrowUpRight,
  SlidersHorizontal,
  Clock3,
  Sparkles,
  Plus,
  KeyRound,
} from "lucide-vue-next";
import { api, post } from "../services/api";
import {
  apiKey,
  stats,
  refreshStats,
  authVersion,
  keyDialogOpen,
} from "../composables/workspace";
import { hasAccess, currentUser } from "../composables/session";
import { useResource } from "../composables/useResource";
import AsyncState from "../components/AsyncState.vue";
import DocCard from "../components/DocCard.vue";
const route = useRoute(),
  router = useRouter();
const query = ref(String(route.query.q || "")),
  domain = ref(String(route.query.domain || ""));
const category = ref(String(route.query.category || ""));
const { data: categoryData } = useResource(() => api("/categories"));
const results = ref([]),
  loading = ref(false),
  error = ref(""),
  searched = ref(false),
  hint = ref("");
const suggestions = ["部署", "数据库", "前端组件", "组织同步", "编码规范"];
const {
  data: recent,
  loading: recentLoading,
  error: recentError,
  reload: loadRecent,
} = useResource(async () => {
  if (!hasAccess.value) return { recent: [] };
  const [recent] = await Promise.all([api("/recent?limit=6"), refreshStats()]);
  return recent;
});
const domains = computed(() => Object.keys(stats.value?.by_domain || {}));
let controller;
async function search(value = query.value) {
  query.value = value;
  if (!value.trim()) return;
  controller?.abort();
  controller = new AbortController();
  const current = controller;
  loading.value = true;
  error.value = "";
  searched.value = true;
  hint.value = "";
  router.replace({
    path: "/workspace",
    query: {
      q: value,
      ...(domain.value ? { domain: domain.value } : {}),
      ...(category.value ? { category: category.value } : {}),
    },
  });
  try {
    const data = await post(
      "/search",
      {
        query: value.trim(),
        domain: domain.value,
        category_id: category.value,
        limit: 20,
      },
      { signal: current.signal },
    );
    results.value = data.results || [];
    hint.value = data.hint || "";
  } catch (e) {
    if (e.name !== "AbortError") error.value = e.message;
  } finally {
    if (current === controller) loading.value = false;
  }
}
function filter(value) {
  domain.value = value;
  if (query.value.trim()) search();
}
watch(authVersion, () => {
  if (query.value.trim()) search();
  else {
    searched.value = false;
    error.value = "";
  }
});
if (query.value.trim()) search();
</script>
<template>
  <section class="search-page">
    <div class="page-heading">
      <div>
        <div class="eyebrow section-eyebrow">
          <span class="tiny-line" /> YOUR KNOWLEDGE, CONNECTED
        </div>
        <h1>让开发有据可循<span class="heading-dot">.</span></h1>
        <p>从平台文档到团队经验，快速找到下一步的答案。</p>
      </div>
      <RouterLink to="/contribute" class="button"
        ><Plus :size="16" />沉淀新知识 <ArrowUpRight :size="15"
      /></RouterLink>
    </div>
    <div class="search-hero">
      <div class="hero-label">
        <span><Sparkles :size="16" /> 团队知识引擎</span
        ><span class="live-label"
          ><span class="status-dot online" />平台知识 · 持续积累</span
        >
      </div>
      <h2>你正在解决什么问题？</h2>
      <p>输入技术关键词、业务场景或待解决的问题，检索你的知识工作空间。</p>
      <form class="search-input-wrap" @submit.prevent="search()">
        <Search :size="22" /><input
          v-model="query"
          data-search-input
          aria-label="搜索知识库"
          placeholder="例如：服务部署、数据库优化、组件设计…"
        /><kbd>⌘ K</kbd
        ><button class="button primary" :disabled="loading || !query.trim()">
          {{ loading ? "检索中…" : "搜索知识" }}<ArrowRight :size="17" />
        </button>
      </form>
      <label class="kb-search-category"
        >分类范围
        <select v-model="category" @change="query.trim() && search()">
          <option value="">全部分类</option>
          <option
            v-for="c in categoryData?.categories"
            :key="c.id"
            :value="c.id"
          >
            {{ c.path }}
          </option>
        </select></label
      >
      <div class="suggestions">
        <span>试试搜索</span
        ><button v-for="item in suggestions" :key="item" @click="search(item)">
          {{ item }}<ArrowUpRight :size="12" />
        </button>
      </div>
    </div>
    <div class="metrics-strip">
      <div>
        <span class="metric-icon"><BookOpen :size="20" /></span>
        <div>
          <strong>{{ stats?.documents ?? "—" }}<small>篇</small></strong
          ><span>知识文档</span>
        </div>
      </div>
      <div>
        <span class="metric-icon violet"><Layers :size="20" /></span>
        <div>
          <strong>{{ stats ? domains.length : "—" }}<small>个</small></strong
          ><span>知识领域</span>
        </div>
      </div>
      <div>
        <span class="metric-icon amber"><Search :size="20" /></span>
        <div>
          <strong
            >{{ stats?.terms?.toLocaleString() ?? "—"
            }}<small>个</small></strong
          ><span>检索词条</span>
        </div>
      </div>
      <div class="metric-note">
        <span class="status-dot online" /><span>连接知识，减少重复探索</span>
      </div>
    </div>
    <div v-if="!hasAccess" class="connect-banner">
      <KeyRound :size="24" />
      <div>
        <strong>注册入网，开启知识探索</strong>
        <p>注册并经管理员审批后，即可使用知识库并管理自己的 Key。</p>
      </div>
      <RouterLink
        class="button primary"
        :to="currentUser ? '/account' : '/register'"
      >
        {{ currentUser ? "查看审批状态" : "注册入网" }}
        <ArrowRight :size="15" />
      </RouterLink>
    </div>
    <section v-if="searched" class="results-section">
      <div class="section-heading">
        <h2>
          检索结果 <span class="count">{{ results.length }}</span>
        </h2>
        <span class="muted">按相关度排序</span>
      </div>
      <div v-if="domains.length" class="filter-row">
        <SlidersHorizontal :size="15" /><button
          :class="['chip', { active: !domain }]"
          @click="filter('')"
        >
          全部领域</button
        ><button
          v-for="item in domains"
          :key="item"
          :class="['chip', { active: domain === item }]"
          @click="filter(item)"
        >
          {{ item }}
        </button>
      </div>
      <AsyncState
        :loading="loading"
        :error="error"
        :empty="!results.length"
        title="没有找到相关文档"
        description="试试更短的关键词，或切换到全部领域。"
        @retry="search()"
        ><p v-if="hint" class="hint result-hint">{{ hint }}</p>
        <div class="document-grid">
          <DocCard v-for="doc in results" :key="doc.id" :doc="doc" /></div
      ></AsyncState>
    </section>
    <template v-else
      ><div class="section-heading">
        <h2>
          <Clock3 :size="19" /> 最近更新<span class="section-caption"
            >知识在这里持续生长</span
          >
        </h2>
        <RouterLink to="/overview" class="text-link"
          >知识总览 <ArrowRight :size="15"
        /></RouterLink>
      </div>
      <AsyncState
        :loading="recentLoading"
        :error="recentError"
        :empty="hasAccess && !recent?.recent?.length"
        title="知识库等待你的第一份积累"
        @retry="loadRecent"
        ><div v-if="recent?.recent?.length" class="document-grid">
          <DocCard v-for="doc in recent.recent" :key="doc.id" :doc="doc" /></div
      ></AsyncState>
      <div class="quick-grid">
        <RouterLink to="/rules" class="quick-card"
          ><span class="feature-icon violet"><BookOpen :size="23" /></span>
          <div>
            <h3>先读规范，再写代码</h3>
            <p>按开发任务获取必读文档与自查清单。</p>
          </div>
          <ArrowUpRight :size="20" /></RouterLink
        ><RouterLink to="/contribute" class="quick-card"
          ><span class="feature-icon amber"><Layers :size="23" /></span>
          <div>
            <h3>把踩过的坑，变成经验</h3>
            <p>记录解法，让团队少走一次弯路。</p>
          </div>
          <ArrowUpRight :size="20"
        /></RouterLink></div
    ></template>
  </section>
</template>
