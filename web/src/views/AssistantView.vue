<script setup>
import AppSelect from "../components/ui/AppSelect.vue";
import { ref, computed, onBeforeUnmount, watch, nextTick } from "vue";
import {
  Bot,
  Send,
  Network,
  ArrowRight,
  Plus,
  UserRound,
  StopCircle,
  RotateCcw,
} from "lucide-vue-next";
import { api, post } from "../services/api";
import { hasAccess } from "../composables/session";
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
  messages = ref([]),
  asked = ref("");
const conversations = ref([]),
  conversationId = ref(""),
  historyLoading = ref(false),
  saveError = ref("");
let historyGeneration = 0,
  saveQueue = Promise.resolve();
const scroll = ref(null);
let controller;
const labels = {
  explore: "知识探索",
  troubleshoot: "排障溯源",
  develop: "开发实施",
  compare: "方案对比",
  learn: "学习路线",
};
const examples = [
  "如何排查组织同步失败？",
  "V5 和 V8 的扩展开发有哪些区别？",
  "我想学习移动开发，应该先看哪些知识？",
];
const hasConversation = computed(() => messages.value.length > 0);
const historyItems = computed(() => conversations.value);
async function saveConversation() {
  if (!messages.value.length || !hasAccess.value) return;
  if (!conversationId.value) conversationId.value = crypto.randomUUID();
  const id = conversationId.value,
    generation = historyGeneration;
  const body = JSON.parse(
    JSON.stringify({
      messages: messages.value,
      category_id: category.value,
      mode: mode.value,
    }),
  );
  saveQueue = saveQueue
    .catch(() => {})
    .then(async () => {
      if (generation !== historyGeneration) return;
      try {
        const saved = await api(
          "/assistant/conversations/" + encodeURIComponent(id),
          { method: "PUT", body },
        );
        if (generation !== historyGeneration) return;
        conversations.value = [
          saved,
          ...conversations.value.filter((c) => c.id !== id),
        ];
        saveError.value = "";
      } catch (e) {
        if (generation === historyGeneration)
          saveError.value = "对话尚未保存：" + e.message;
      }
    });
  await saveQueue;
}
async function selectHistory(item) {
  if (busy.value || historyLoading.value) return;
  await saveQueue.catch(() => {});
  const generation = historyGeneration;
  historyLoading.value = true;
  try {
    const data = await api(
      "/assistant/conversations/" + encodeURIComponent(item.id),
    );
    if (generation !== historyGeneration) return;
    conversationId.value = item.id;
    messages.value = data.messages || [];
    category.value = data.category_id || "";
    mode.value = data.mode || "auto";
    question.value = "";
    error.value = "";
  } catch (e) {
    if (generation === historyGeneration) saveError.value = e.message;
  } finally {
    if (generation === historyGeneration) historyLoading.value = false;
  }
}
async function restoreHistory() {
  const generation = ++historyGeneration;
  controller?.abort();
  busy.value = false;
  messages.value = [];
  conversations.value = [];
  conversationId.value = "";
  question.value = "";
  error.value = "";
  saveError.value = "";
  historyLoading.value = false;
  if (!hasAccess.value) return;
  historyLoading.value = true;
  try {
    const data = await api("/assistant/conversations");
    if (generation !== historyGeneration) return;
    conversations.value = data.conversations || [];
    if (conversations.value.length) {
      const item = conversations.value[0];
      const saved = await api(
        "/assistant/conversations/" + encodeURIComponent(item.id),
      );
      if (generation !== historyGeneration) return;
      conversationId.value = item.id;
      messages.value = saved.messages || [];
      category.value = saved.category_id || "";
      mode.value = saved.mode || "auto";
    }
  } catch (e) {
    if (generation === historyGeneration)
      saveError.value = "历史记录加载失败：" + e.message;
  } finally {
    if (generation === historyGeneration) historyLoading.value = false;
  }
}

watch(
  () => [messages.value.length, busy.value],
  async () => {
    await nextTick();
    scroll.value?.scrollTo({
      top: scroll.value.scrollHeight,
      behavior: "smooth",
    });
  },
);
async function ask(value = question.value) {
  const text = value.trim();
  if (!text || busy.value || historyLoading.value) return;
  question.value = "";
  asked.value = text;
  error.value = "";
  busy.value = true;
  controller = new AbortController();
  const requestController = controller;
  const previous = messages.value
    .filter((m) => m.role === "user" || m.role === "assistant")
    .slice(-8)
    .map((m) => ({ role: m.role, content: m.content.slice(0, 4000) }));
  messages.value.push({ role: "user", content: text, time: Date.now() });
  saveConversation();
  await nextTick();
  scroll.value?.scrollTo({
    top: scroll.value.scrollHeight,
    behavior: "smooth",
  });
  try {
    const answer = await post(
      "/assistant/ask",
      {
        question: text,
        category_id: category.value,
        scenario: scenario.value,
        mode: mode.value,
        history: previous,
      },
      { signal: requestController.signal },
    );
    if (requestController.signal.aborted) return;
    messages.value.push({
      role: "assistant",
      content: answer.answer,
      answer,
      time: Date.now(),
    });
  } catch (e) {
    if (e.name !== "AbortError") {
      error.value = e.message;
      messages.value.push({
        role: "error",
        content: e.message,
        time: Date.now(),
      });
    }
  } finally {
    if (controller === requestController) {
      busy.value = false;
      if (!requestController.signal.aborted) await saveConversation();
    }
  }
}
function cancel() {
  controller?.abort();
  busy.value = false;
  error.value = "已停止本次等待。";
}
function clearChat() {
  controller?.abort();
  busy.value = false;
  conversationId.value = "";
  messages.value = [];
  question.value = "";
  error.value = "";
}
function retry() {
  const last = [...messages.value].reverse().find((m) => m.role === "user");
  if (last) {
    messages.value = messages.value.filter(
      (m) => m !== last && m.role !== "error" && m.time < last.time,
    );
    ask(last.content);
  }
}
watch(authVersion, restoreHistory, { immediate: true });
onBeforeUnmount(() => controller?.abort());
</script>
<template>
  <section class="intelligence-page assistant-page assistant-chat-page">
    <div class="page-heading assistant-chat-heading">
      <div>
        <div class="eyebrow section-eyebrow">TEAM KNOWLEDGE ASSISTANT</div>
        <h1>云端智能体</h1>
        <p>基于团队知识库连续对话，回答附带可核验的原文和版本。</p>
      </div>
      <div class="assistant-heading-actions">
        <button v-if="hasConversation" class="button" @click="clearChat">
          <Plus :size="15" />新对话</button
        ><RouterLink to="/graph" class="button"
          ><Network :size="16" />知识链</RouterLink
        >
      </div>
    </div>
    <div class="assistant-chat-shell panel">
      <aside class="assistant-chat-sidebar">
        <div class="assistant-sidebar-brand">
          <span class="assistant-avatar"><Bot :size="21" /></span>
          <div>
            <strong>TeamKB Agent</strong
            ><small>{{
              status?.ready ? "知识服务在线" : "等待模型配置"
            }}</small>
          </div>
        </div>
        <div class="assistant-sidebar-section assistant-history-section">
          <div class="assistant-history-title">
            <span>对话历史</span
            ><small v-if="historyItems.length"
              >{{ historyItems.length }} 条</small
            >
          </div>
          <button
            v-for="item in historyItems"
            :key="item.id"
            class="assistant-history-item"
            @click="selectHistory(item)"
            :title="item.title"
            :disabled="busy || historyLoading"
          >
            <span>{{ item.title }}</span><ArrowRight :size="13" />
          </button>
          <p v-if="!historyItems.length" class="assistant-history-empty">
            {{ historyLoading ? "正在加载历史…" : "当前还没有对话记录" }}
          </p>
        </div>
        <div class="assistant-sidebar-footer">
          <span
            class="status-dot"
            :class="{ online: status?.ready }"
          />只使用已发布知识
        </div>
      </aside>
      <div class="assistant-chat-main">
        <div
          ref="scroll"
          class="assistant-chat-messages"
          :class="{ 'is-empty': !hasConversation }"
        >
          <div v-if="!hasConversation" class="assistant-chat-welcome">
            <span class="assistant-welcome-icon"><Bot :size="30" /></span>
            <h2>今天想了解什么？</h2>
            <p>
              描述问题、产品版本和已尝试的方法，我会从团队知识库中整理依据。
            </p>
            <div class="assistant-welcome-prompts">
              <button v-for="q in examples" :key="q" @click="question = q">
                {{ q }}
              </button>
            </div>
          </div>
          <template
            v-for="(message, index) in messages"
            :key="message.time + '-' + index"
          >
            <div
              v-if="message.role === 'user'"
              class="assistant-message user-message"
              :data-message-time="message.time"
            >
              <span class="message-avatar"><UserRound :size="15" /></span>
              <div class="message-bubble">{{ message.content }}</div>
            </div>
            <article
              v-else-if="message.role === 'assistant'"
              class="assistant-message assistant-message"
            >
              <span class="message-avatar"><Bot :size="15" /></span>
              <div class="message-content">
                <div class="message-bubble assistant-bubble">
                  <div class="message-answer-badge">
                    {{ labels[message.answer?.scenario] || "知识分析" }} ·
                    {{
                      message.answer?.mode === "chain"
                        ? "知识链分析"
                        : "分类检索"
                    }}
                  </div>
                  <MarkdownContent :content="message.content" />
                </div>
                <details
                  v-if="message.answer?.trace?.length"
                  class="assistant-reasoning"
                >
                  <summary>查看分析过程</summary>
                  <div class="assistant-trace-list">
                    <div
                      v-for="(step, traceIndex) in message.answer.trace"
                      :key="traceIndex"
                      class="assistant-trace-step"
                    >
                      <span>{{ traceIndex + 1 }}</span>
                      <div>
                        <strong>{{ step.step }}</strong><small>{{
                          step.detail
                        }}</small>
                      </div>
                    </div>
                  </div>
                </details>
                <div v-if="message.answer" class="message-sources">
                  <span class="badge">{{
                    labels[message.answer.scenario] || "知识分析"
                  }}</span><span class="badge">{{
                    message.answer.mode === "chain" ? "知识链分析" : "分类检索"
                  }}</span>
                  <details v-if="message.answer.citations?.length">
                    <summary>
                      查看 {{ message.answer.citations.length }} 条依据
                    </summary>
                    <div
                      v-for="c in message.answer.citations"
                      :key="c.id"
                      class="chat-citation"
                    >
                      <RouterLink :to="'/documents/' + encodeURIComponent(c.id)"
                        >[{{ c.number }}] {{ c.title }}</RouterLink
                      ><small
                        >v{{ c.version }} ·
                        {{ c.truncated ? "节选资料" : "完整资料" }}</small
                      ><RouterLink
                        :to="{ path: '/graph', query: { doc: c.id } }"
                        class="text-link"
                        >查看知识链 →</RouterLink
                      >
                    </div>
                  </details>
                  <RouterLink
                    v-if="message.answer.citations?.length"
                    :to="{
                      path: '/graph',
                      query: { doc: message.answer.citations[0].id },
                    }"
                    class="text-link chat-chain-link"
                    >查看知识链 →</RouterLink
                  >
                </div>
              </div>
            </article>
            <div v-else class="assistant-message assistant-error">
              <span class="message-avatar"><Bot :size="15" /></span>
              <div class="message-bubble">
                {{ message.content
                }}<button
                  class="text-link retry-chat"
                  :disabled="busy"
                  @click="retry"
                >
                  <RotateCcw :size="13" />重试
                </button>
              </div>
            </div>
          </template>
          <div v-if="busy" class="assistant-message assistant-message">
            <span class="message-avatar"><Bot :size="15" /></span>
            <div class="message-bubble thinking-bubble">
              <i></i><i></i><i></i><span>正在检索知识并整理依据…</span>
            </div>
          </div>
        </div>
        <div v-if="statusError" class="assistant-inline-error" role="alert">
          {{ statusError }}
          <button class="text-link" @click="reloadStatus">重新检查</button>
        </div>
        <div v-else-if="!status?.ready" class="assistant-inline-error">
          <h3>模型服务尚未启用</h3>
          请联系管理员在工作台管理中配置。
        </div>
        <p v-if="saveError" class="assistant-inline-error" role="alert">
          {{ saveError }}
          <button type="button" class="text-link" @click="saveConversation">
            重试保存
          </button>
        </p>
        <p
          v-if="error && !messages.some((m) => m.role === 'error')"
          class="assistant-inline-error"
          role="status"
        >
          {{ error }}
        </p>
        <form
          class="assistant-chat-composer"
          @submit.prevent="busy ? cancel() : ask()"
        >
          <div class="assistant-composer-options">
            <AppSelect v-model="category" aria-label="知识范围"
              ><option value="">全部知识</option>
              <option
                v-for="c in categories?.categories || []"
                :key="c.id"
                :value="c.id"
              >
                {{ c.path }}
              </option></AppSelect
            ><AppSelect v-model="mode" aria-label="检索方式"
              ><option value="auto">智能检索</option>
              <option value="search">分类检索</option>
              <option value="chain">知识链分析</option></AppSelect
            >
          </div>
          <textarea
            id="agent-question"
            v-model="question"
            required
            minlength="2"
            maxlength="1200"
            rows="2"
            placeholder="继续提问…"
            :disabled="busy"
            @keydown.enter.exact="
              !$event.isComposing &&
              ($event.preventDefault(),
              !busy && status?.ready && question.trim().length >= 2 && ask())
            "
            aria-label="知识问答问题"
          />
          <div class="assistant-composer-bottom">
            <small>回答仅基于已发布团队知识，引用可展开核验</small
            ><button v-if="busy" type="button" @click="cancel" class="button">
              <StopCircle :size="15" />停止</button
            ><button
              v-else
              type="submit"
              class="button primary"
              :disabled="
                historyLoading || !status?.ready || question.trim().length < 2
              "
            >
              <Send :size="15" />发送
            </button>
          </div>
        </form>
      </div>
    </div>
  </section>
</template>
