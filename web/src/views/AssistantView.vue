<script setup>
import AppSelect from "../components/ui/AppSelect.vue";
import { ref, onBeforeUnmount, watch } from "vue";
import { Bot, Send, Network, ArrowRight } from "lucide-vue-next";
import { api, post } from "../services/api";
import { authVersion } from "../composables/workspace";
import { useResource } from "../composables/useResource";
import MarkdownContent from "../components/MarkdownContent.vue";
import "../styles/intelligence.css";
const {
  data: status,
  error: statusError,
  reload: reloadStatus,
} = useResource(() => api("/assistant/status"));
const { data: categories } = useResource(() => api("/categories"));
const question = ref(""),
  category = ref(""),
  scenario = ref("auto"),
  mode = ref("auto"),
  busy = ref(false),
  error = ref(""),
  answer = ref(null),
  asked = ref("");
let controller;
async function ask(value = question.value) {
  if (!value.trim() || busy.value) return;
  question.value = value;
  asked.value = value;
  controller = new AbortController();
  busy.value = true;
  error.value = "";
  answer.value = null;
  try {
    answer.value = await post(
      "/assistant/ask",
      {
        question: value.trim(),
        category_id: category.value,
        scenario: scenario.value,
        mode: mode.value,
      },
      { signal: controller.signal },
    );
  } catch (e) {
    if (e.name !== "AbortError") error.value = e.message;
  } finally {
    busy.value = false;
  }
}
function cancel() {
  controller?.abort();
  busy.value = false;
  error.value = "已停止等待；模型服务可能仍在完成本次请求。";
}
watch(authVersion, () => {
  controller?.abort();
  answer.value = null;
  question.value = "";
  asked.value = "";
});
onBeforeUnmount(() => controller?.abort());
const labels = {
  explore: "知识探索",
  troubleshoot: "排障溯源",
  develop: "开发实施",
  compare: "方案对比",
  learn: "学习路线",
};
</script>
<template>
  <section class="intelligence-page assistant-page">
    <div class="page-heading">
      <div>
        <div class="eyebrow section-eyebrow">GROUNDED TEAM INTELLIGENCE</div>
        <h1>云端智能体</h1>
        <p>先找依据，再沿知识链分析。回答附带原文和版本，方便你核验。</p>
      </div>
      <RouterLink to="/graph" class="button"
        ><Network :size="16" />知识链</RouterLink
      >
    </div>
    <div class="assistant-hero panel">
      <span class="assistant-avatar"><Bot :size="30" /></span>
      <h2>把问题交给团队知识库</h2>
      <p>排查问题、规划开发、比较方案，或找到一条学习路线。</p>
      <div class="assistant-examples">
        <button
          v-for="q in [
            '如何排查组织同步失败？',
            'V5 和 V8 的扩展开发有哪些区别？',
            '我想学习移动开发，应该先看哪些知识？',
          ]"
          :key="q"
          :disabled="busy"
          @click="question = q"
        >
          {{ q }} <ArrowRight :size="13" />
        </button>
      </div>
    </div>
    <div v-if="statusError" class="panel">
      <p role="alert" class="error-text">{{ statusError }}</p>
      <button class="button" @click="reloadStatus">重新检查</button>
    </div>
    <div
      v-else-if="status && !status.ready"
      class="panel assistant-unconfigured"
    >
      <Bot :size="23" />
      <div>
        <h3>模型服务尚未启用</h3>
        <p>
          管理员可在工作台管理配置兼容 OpenAI
          协议的模型服务。当前仍可使用知识检索与知识链。
        </p>
      </div>
      <RouterLink to="/admin" class="button">查看管理配置</RouterLink>
    </div>
    <form class="panel assistant-form" @submit.prevent="ask()">
      <div class="assistant-options">
        <label class="field"
          >知识范围<AppSelect v-model="category">
            <option value="">自动识别 / 全部知识</option>
            <option
              v-for="c in categories?.categories || []"
              :key="c.id"
              :value="c.id"
            >
              {{ c.path }}
            </option>
          </AppSelect></label
        ><label class="field"
          >使用场景<AppSelect v-model="scenario">
            <option value="auto">智能判断</option>
            <option v-for="(label, id) in labels" :key="id" :value="id">
              {{ label }}
            </option>
          </AppSelect></label
        ><label class="field"
          >检索方式<AppSelect v-model="mode">
            <option value="auto">按场景自动选择</option>
            <option value="search">分类检索</option>
            <option value="chain">知识链分析</option>
          </AppSelect></label
        >
      </div>
      <label class="sr-only" for="agent-question">知识问答问题</label
      ><textarea
        id="agent-question"
        v-model="question"
        required
        minlength="2"
        maxlength="1200"
        rows="4"
        placeholder="描述问题、产品版本与已尝试的方法…"
        :disabled="busy"
      />
      <div class="assistant-submit">
        <small
          >只使用已发布知识。问题及相关片段会发送至管理员配置的模型服务。</small
        ><button v-if="busy" type="button" class="button" @click="cancel">
          停止等待</button
        ><button
          v-else
          class="button primary"
          :disabled="!status?.ready || question.trim().length < 2"
        >
          <Send :size="15" />开始分析
        </button>
      </div>
    </form>
    <p v-if="busy" class="assistant-thinking" role="status">
      正在检索知识、整理关联与引用…
    </p>
    <p v-if="error" role="alert" class="error-text">{{ error }}</p>
    <div v-if="answer" class="assistant-answer-grid">
      <article class="panel assistant-answer">
        <div class="assistant-answer-meta">
          <span class="badge">{{ labels[answer.scenario] }}</span><span
            class="badge"
            >{{ answer.mode === "chain" ? "知识链分析" : "分类检索" }}</span
          ><small>{{ answer.model }}</small>
        </div>
        <h2>{{ asked }}</h2>
        <p v-if="answer.status !== 'answered'" class="intelligence-muted">
          本次没有生成可验证的结论。
        </p>
        <MarkdownContent :content="answer.answer" />
        <p class="intelligence-muted">
          数字引用对应右侧来源。回答中的引用可定位资料，但仍需核对具体适用版本。
        </p>
      </article>
      <aside class="panel assistant-sources">
        <h2>
          依据与引用 <span class="badge">{{ answer.citations.length }}</span>
        </h2>
        <div v-for="c in answer.citations" :key="c.id" class="assistant-source">
          <RouterLink :to="'/documents/' + encodeURIComponent(c.id)"
            ><strong>[{{ c.number }}] {{ c.title }}</strong></RouterLink
          ><small
            >文档版本 v{{ c.version }} ·
            {{ c.truncated ? "节选资料" : "完整资料" }}</small
          >
          <p>{{ c.excerpt }}</p>
          <RouterLink
            :to="{ path: '/graph', query: { doc: c.id } }"
            class="text-link"
            >查看知识链 →</RouterLink
          >
        </div>
        <p v-if="!answer.citations.length" class="intelligence-muted">
          没有找到相关文档。
        </p>
        <details v-if="answer.chain.length">
          <summary>本次使用的 {{ answer.chain.length }} 条知识关系</summary>
          <p v-for="e in answer.chain" :key="e.id" class="intelligence-muted">
            {{ e.label }} ·
            {{ e.origin === "manual" ? "人工维护" : "正文引用" }}
          </p>
        </details>
      </aside>
    </div>
  </section>
</template>
