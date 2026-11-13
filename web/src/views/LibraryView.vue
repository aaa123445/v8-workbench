<script setup>
import { ref, computed, watch, onBeforeUnmount } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  Folder,
  FolderOpen,
  FolderTree,
  BookOpen,
  Plus,
  Search,
  LayoutGrid,
  List,
  ChevronDown,
  ChevronRight,
  ArrowUpRight,
  SlidersHorizontal,
  X,
  ArrowLeft,
  ArrowRight,
  CheckCheck,
  Layers,
} from "lucide-vue-next";
import { api } from "../services/api";
import { currentUser, isAdmin } from "../composables/session";
import { stats } from "../composables/workspace";
import { useResource } from "../composables/useResource";
import { categoryTone } from "../utils/format";
import AsyncState from "../components/AsyncState.vue";
import KnowledgeCard from "../components/workspace/KnowledgeCard.vue";
const route = useRoute(),
  router = useRouter(),
  query = ref(String(route.query.q || "")),
  view = ref(
    localStorage.getItem("teamkb_library_view") === "list"
      ? "list"
      : localStorage.getItem("teamkb_library_view") === "grid"
        ? "grid"
        : window.matchMedia("(max-width:600px)").matches
          ? "list"
          : "grid",
  ),
  collapsed = ref(new Set());
const category = computed(() => String(route.query.category || "")),
  page = computed(() => Math.max(1, Number(route.query.page) || 1)),
  sort = computed(() => route.query.sort || "updated"),
  pageSize = 12;
const { data: categoryData } = useResource(() => api("/categories"));
const categories = computed(() => categoryData.value?.categories || []),
  categoryMap = computed(() => new Map(categories.value.map((c) => [c.id, c]))),
  selected = computed(() => categoryMap.value.get(category.value));
const roots = computed(() => categories.value.filter((c) => !c.parent_id));
const collections = computed(() =>
  [...roots.value]
    .sort(
      (a, b) =>
        (b.total_documents ?? b.documents) - (a.total_documents ?? a.documents),
    )
    .slice(0, 4),
);
const visibleCategories = computed(() =>
  categories.value.filter((c) => {
    let parent = categoryMap.value.get(c.parent_id);
    while (parent) {
      if (collapsed.value.has(parent.id)) return false;
      parent = categoryMap.value.get(parent.parent_id);
    }
    return true;
  }),
);
const descendantsCount = computed(() =>
  categories.value.reduce((n, c) => n + (c.documents || 0), 0),
);
const { data, loading, error, reload } = useResource(
  () =>
    api(
      "/library?" +
        new URLSearchParams({
          category_id: category.value,
          query: route.query.q || "",
          tag: route.query.tag || "",
          page: page.value,
          page_size: pageSize,
          sort: sort.value,
        }),
    ),
  [() => route.fullPath],
);
let timer;
function filter(values) {
  clearTimeout(timer);
  router.replace({
    path: "/library",
    query: { ...route.query, page: undefined, ...values },
  });
}
watch(query, (value) => {
  clearTimeout(timer);
  if (value !== String(route.query.q || ""))
    timer = setTimeout(() => filter({ q: value.trim() || undefined }), 350);
});
watch(
  () => route.query.q,
  (value) => {
    query.value = String(value || "");
  },
);
watch(view, (value) => localStorage.setItem("teamkb_library_view", value));
watch(category, (cid) => {
  const next = new Set(collapsed.value);
  let parent = categoryMap.value.get(cid);
  while (parent) {
    next.delete(parent.id);
    parent = categoryMap.value.get(parent.parent_id);
  }
  collapsed.value = next;
});
onBeforeUnmount(() => clearTimeout(timer));
function toggle(cid) {
  const next = new Set(collapsed.value);
  if (next.has(cid)) next.delete(cid);
  else next.add(cid);
  collapsed.value = next;
}
function clear() {
  query.value = "";
  filter({ q: undefined, tag: undefined, category: undefined });
}
const totalPages = computed(() =>
  Math.max(1, Math.ceil((data.value?.total || 0) / pageSize)),
);
</script>
<template>
  <section class="library-page">
    <div class="page-heading">
      <div>
        <div class="eyebrow section-eyebrow">YOUR TEAM, CONNECTED</div>
        <h1>团队知识库<span class="title-dot">.</span></h1>
        <p>
          {{
            currentUser ? currentUser.display_name + "，欢迎回来。" : ""
          }}把分散的经验，连接成团队共同的答案。
        </p>
      </div>
      <RouterLink to="/contribute" class="button primary"
        ><Plus :size="17" />贡献知识</RouterLink
      >
    </div>
    <div class="library-intro">
      <div>
        <span class="library-intro-label"
          ><span class="status-dot online" />团队共享空间</span
        >
        <h2>好的经验，值得被下一次遇见。</h2>
        <p>从文档找到依据，让验证过的方案成为下一次协作的起点。</p>
        <div class="library-intro-links">
          <RouterLink to="/workspace"
            >探索知识 <ArrowUpRight :size="14" /></RouterLink
          ><RouterLink to="/guide"
            >连接你的 Agent <ArrowUpRight :size="14"
          /></RouterLink>
        </div>
      </div>
      <div class="intro-illustration" aria-hidden="true">
        <span class="intro-sheet sheet-back" /><span
          class="intro-sheet sheet-front"
          ><BookOpen :size="29" /><i /><i /><i /></span
        ><span class="intro-check"><CheckCheck :size="22" /></span
        ><span class="intro-orbit" />
      </div>
      <div class="library-intro-stat">
        <strong
          >{{ stats?.documents ?? descendantsCount }}<span>篇</span></strong
        ><small>团队知识 · 持续积累</small>
      </div>
    </div>
    <div class="collections-heading">
      <h2><FolderTree :size="17" />知识分类</h2>
      <RouterLink v-if="isAdmin" to="/categories"
        >管理分类 <ArrowUpRight :size="13"
      /></RouterLink>
    </div>
    <div class="collection-grid">
      <button
        v-for="c in collections"
        :key="c.id"
        :class="[
          'collection-card',
          'tone-' + categoryTone(c.id),
          { active: category === c.id },
        ]"
        @click="filter({ category: category === c.id ? undefined : c.id })"
      >
        <span class="collection-icon"><Folder :size="25" /></span
        ><span
          ><strong>{{ c.name }}</strong
          ><small>{{ c.total_documents ?? c.documents }} 篇知识</small></span
        ><ArrowUpRight :size="15" />
      </button>
    </div>
    <div class="kb-library">
      <aside class="kb-taxonomy">
        <div class="taxonomy-heading">
          <span><Layers :size="15" />分类目录</span
          ><span>{{ roots.length }}</span>
        </div>
        <div
          class="taxonomy-scroll"
          tabindex="0"
          role="region"
          aria-label="知识分类目录"
        >
          <button
            :class="['taxonomy-all', { active: !category }]"
            @click="filter({ category: undefined })"
          >
            <BookOpen :size="16" /><span>全部知识</span
            ><small>{{ stats?.documents ?? descendantsCount }}</small>
          </button>
          <div
            v-for="c in visibleCategories"
            :key="c.id"
            class="taxonomy-row"
            :style="{ '--depth': c.path.split(' / ').length - 1 }"
          >
            <button
              v-if="categories.some((child) => child.parent_id === c.id)"
              class="taxonomy-expander"
              :aria-label="(collapsed.has(c.id) ? '展开' : '收起') + c.name"
              :aria-expanded="!collapsed.has(c.id)"
              @click="toggle(c.id)"
            >
              <ChevronRight v-if="collapsed.has(c.id)" :size="12" /><ChevronDown
                v-else
                :size="12"
              /></button
            ><button
              :class="['taxonomy-item', { active: category === c.id }]"
              :title="c.path"
              @click="filter({ category: c.id })"
            >
              <FolderOpen v-if="category === c.id" :size="16" /><Folder
                v-else
                :size="16"
              /><span>{{ c.name }}</span
              ><small>{{ c.total_documents ?? c.documents }}</small>
            </button>
          </div>
        </div>
        <div class="taxonomy-footnote">
          <span class="status-dot online" />审核发布后，团队成员可见
        </div>
      </aside>
      <div class="library-content">
        <div class="library-toolbar">
          <form
            class="library-search"
            @submit.prevent="filter({ q: query.trim() || undefined })"
          >
            <Search :size="17" /><input
              v-model="query"
              aria-label="筛选知识"
              placeholder="搜索知识标题或摘要…"
              autocomplete="off"
            /><button
              v-if="query"
              class="icon-button"
              type="button"
              aria-label="清除知识筛选"
              @click="
                query = '';
                filter({ q: undefined });
              "
            >
              <X :size="14" /></button
            ><button class="sr-only" type="submit">筛选</button>
          </form>
          <div class="library-toolbar-actions">
            <label class="sort-control"
              ><SlidersHorizontal :size="14" /><select
                :value="sort"
                aria-label="知识排序"
                @change="filter({ sort: $event.target.value })"
              >
                <option value="updated">最近更新</option>
                <option value="title">标题排序</option>
                <option value="oldest">最早更新</option>
              </select></label
            >
            <div class="view-toggle" aria-label="知识显示方式">
              <button
                :class="{ active: view === 'grid' }"
                aria-label="卡片视图"
                :aria-pressed="view === 'grid'"
                @click="view = 'grid'"
              >
                <LayoutGrid :size="17" /></button
              ><button
                :class="{ active: view === 'list' }"
                aria-label="列表视图"
                :aria-pressed="view === 'list'"
                @click="view = 'list'"
              >
                <List :size="18" />
              </button>
            </div>
          </div>
        </div>
        <div class="kb-list-heading">
          <h2>
            {{ selected?.path || "全部知识"
            }}<span>{{ data?.total ?? "—" }}</span>
          </h2>
          <RouterLink
            :to="{
              path: '/workspace',
              query: { q: query || undefined, category: category || undefined },
            }"
            class="text-link"
            >全文检索 <ArrowUpRight :size="13"
          /></RouterLink>
        </div>
        <div v-if="route.query.q || route.query.tag" class="active-filters">
          <span v-if="route.query.q">关键词：{{ route.query.q }}</span
          ><button v-if="route.query.tag" @click="filter({ tag: undefined })">
            标签：{{ route.query.tag }}<X :size="12" /></button
          ><button
            class="text-link"
            @click="
              query = '';
              filter({ q: undefined, tag: undefined });
            "
          >
            清除筛选
          </button>
        </div>
        <AsyncState
          variant="cards"
          :loading="loading"
          :error="error"
          @retry="reload"
          ><div
            v-if="data?.documents?.length"
            :class="['kb-cards', { 'is-list': view === 'list' }]"
          >
            <KnowledgeCard
              v-for="d in data.documents"
              :key="d.id"
              :doc="d"
              :category="categoryMap.get(d.category_id)"
              @tag="filter({ tag: $event })"
            />
          </div>
          <div v-else class="library-empty">
            <span
              ><Search v-if="query || route.query.tag" :size="28" /><FolderOpen
                v-else
                :size="28"
            /></span>
            <h3>
              {{
                query || route.query.tag
                  ? "没有找到匹配的知识"
                  : "这里的知识，等待你来点亮"
              }}
            </h3>
            <p>
              {{
                query || route.query.tag
                  ? "换个关键词，或清除筛选继续探索。"
                  : "分享一个真实验证的解法，让团队的下一次探索更轻松。"
              }}
            </p>
            <button
              v-if="query || route.query.tag"
              class="button"
              @click="clear"
            >
              清除筛选</button
            ><RouterLink v-else to="/contribute" class="button primary"
              ><Plus :size="15" />贡献第一份知识</RouterLink
            >
          </div>
          <div v-if="data?.total" class="kb-pagination">
            <span
              >{{ (page - 1) * pageSize + 1 }}–{{
                Math.min(page * pageSize, data.total)
              }}
              / 共 {{ data.total }} 篇</span
            >
            <div>
              <button
                class="button small"
                :disabled="page <= 1"
                aria-label="上一页"
                @click="
                  router.replace({ query: { ...route.query, page: page - 1 } })
                "
              >
                <ArrowLeft :size="14" /></button
              ><span>{{ page }} / {{ totalPages }}</span
              ><button
                class="button small"
                :disabled="page >= totalPages"
                aria-label="下一页"
                @click="
                  router.replace({ query: { ...route.query, page: page + 1 } })
                "
              >
                <ArrowRight :size="14" />
              </button>
            </div></div
        ></AsyncState>
      </div>
    </div>
  </section>
</template>
