<script setup>
import { computed } from "vue";
import { BookOpen, Layers, Text, Bot, RefreshCw } from "lucide-vue-next";
import { refreshStats, sourceLabel } from "../composables/workspace";
import { useResource } from "../composables/useResource";
import AsyncState from "../components/AsyncState.vue";
const { data, loading, error, reload } = useResource(refreshStats);
const domains = computed(() =>
  Object.entries(data.value?.by_domain || {}).sort((a, b) => b[1] - a[1]),
);
const sources = computed(() => Object.entries(data.value?.by_source || {}));
const max = computed(() => Math.max(1, ...domains.value.map((x) => x[1])));
</script>
<template>
  <section>
    <div class="page-heading">
      <div>
        <div class="eyebrow section-eyebrow">A LIVING KNOWLEDGE BASE</div>
        <h1>知识总览</h1>
        <p>看见知识的积累，也发现值得继续探索的领域。</p>
      </div>
      <button class="button" :disabled="loading" @click="reload">
        <RefreshCw :size="15" :class="{ spin: loading }" />刷新数据
      </button>
    </div>
    <AsyncState :loading="loading" :error="error" @retry="reload"
      ><template v-if="data"
        ><div class="stat-grid">
          <div
            v-for="item in [
              {
                label: '知识文档',
                value: data.documents,
                icon: BookOpen,
                caption: '团队知识的持续积累',
              },
              {
                label: '知识领域',
                value: domains.length,
                icon: Layers,
                caption: '覆盖平台开发场景',
              },
              {
                label: '索引词条',
                value: data.terms,
                icon: Text,
                caption: '让每一条经验可被发现',
              },
              {
                label: 'Agent 沉淀',
                value: data.by_source?.agent || 0,
                icon: Bot,
                caption: '人机协同的经验记录',
              },
            ]"
            :key="item.label"
            class="panel stat-card"
          >
            <div>
              <span>{{ item.label }}</span><component
                :is="item.icon"
                :size="20"
              />
            </div>
            <strong>{{ item.value?.toLocaleString() ?? "—" }}</strong>
            <p>{{ item.caption }}</p>
          </div>
        </div>
        <div class="two-columns">
          <div class="panel">
            <div class="section-heading">
              <h2>知识领域分布</h2>
              <span class="muted">{{ domains.length }} 个领域</span>
            </div>
            <div v-for="[name, count] in domains" :key="name" class="bar-item">
              <div>
                <span>{{ name }}</span><strong
                  >{{ count }} <small>篇</small></strong
                >
              </div>
              <div class="bar-track">
                <span :style="{ width: `${(count / max) * 100}%` }" />
              </div>
            </div>
            <p v-if="!domains.length" class="muted">暂无领域数据。</p>
          </div>
          <div class="panel">
            <div class="section-heading">
              <h2>知识来源</h2>
              <Layers :size="19" />
            </div>
            <div
              v-for="[name, count] in sources"
              :key="name"
              class="source-row"
            >
              <span class="file-icon"><BookOpen :size="18" /></span>
              <div>
                <strong>{{ sourceLabel(name) }}</strong><span
                  >{{
                    data.documents
                      ? Math.round((count / data.documents) * 100)
                      : 0
                  }}% 的知识文档</span
                >
              </div>
              <b>{{ count }}</b>
            </div>
            <div class="overview-note">
              <strong>让知识库保持生长</strong>
              <p>通过语雀同步和团队经验沉淀，持续完善知识覆盖。</p>
              <RouterLink to="/contribute" class="text-link"
                >分享你的经验 →</RouterLink
              >
            </div>
          </div>
        </div></template
      ></AsyncState
    >
  </section>
</template>
