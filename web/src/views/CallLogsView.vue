<script setup>
import { ref, reactive, computed } from "vue";
import {
  Activity,
  RefreshCw,
  Search,
  ChevronLeft,
  ChevronRight,
  ArrowUpRight,
} from "lucide-vue-next";
import { api } from "../services/api";
import { hasAccess, currentUser } from "../composables/session";
import { notify, keyDialogOpen } from "../composables/workspace";
import { useResource } from "../composables/useResource";
import {
  operations,
  clients,
  outcomes,
  formatTime,
  formatDuration,
} from "../utils/callLogs";
import AsyncState from "../components/AsyncState.vue";
import CallLogDetail from "../components/CallLogDetail.vue";
import "../styles/call-logs.css";
const page = ref(1),
  pageSize = ref(20),
  applied = ref({}),
  selected = ref(null);
const draft = reactive({
  query: "",
  operation: "",
  client: "",
  outcome: "",
  key_prefix: "",
  from: "",
  to: "",
});
const { data, loading, error, reload } = useResource(async () => {
  if (!hasAccess.value) return null;
  const params = new URLSearchParams({
    ...applied.value,
    page: page.value,
    page_size: pageSize.value,
  });
  return api("/account/calls?" + params);
}, [page, pageSize, applied]);
const pages = computed(() =>
  Math.max(1, Math.ceil((data.value?.total || 0) / pageSize.value)),
);
const stats = computed(() => [
  { label: "当前筛选调用", value: data.value?.summary.total },
  { label: "成功调用", value: data.value?.summary.success },
  { label: "失败调用", value: data.value?.summary.failed },
  {
    label: "平均耗时",
    value: data.value
      ? formatDuration(data.value.summary.avg_duration_ms)
      : undefined,
  },
]);
function apply() {
  if (draft.from && draft.to && draft.from > draft.to) {
    notify("开始日期不能晚于结束日期", "error");
    return;
  }
  const values = Object.fromEntries(
    Object.entries(draft).filter(
      ([key, value]) => value && !["from", "to"].includes(key),
    ),
  );
  if (draft.from)
    values.since = Math.floor(
      new Date(draft.from + "T00:00:00").getTime() / 1000,
    );
  if (draft.to) {
    const end = new Date(draft.to + "T00:00:00");
    end.setDate(end.getDate() + 1);
    values.until = Math.floor(end.getTime() / 1000);
  }
  applied.value = values;
  page.value = 1;
}
function reset() {
  for (const key of Object.keys(draft)) draft[key] = "";
  apply();
}
function resize() {
  page.value = 1;
}
</script>
<template>
  <section class="call-logs-page">
    <div class="page-heading">
      <div>
        <div class="eyebrow section-eyebrow">YOUR ACTIVITY, IN CONTEXT</div>
        <h1>我的调用日志</h1>
        <p>
          回溯知识调用的请求、状态与结果，网页和个人 Key 的调用都能找到依据。
        </p>
      </div>
      <button class="button" :disabled="loading || !hasAccess" @click="reload">
        <RefreshCw :class="{ spin: loading }" :size="15" />刷新日志
      </button>
    </div>
    <div v-if="!hasAccess" class="panel account-login-prompt">
      <Activity :size="32" />
      <h2>
        {{
          currentUser
            ? "账号获批后可查询个人调用记录"
            : "登录后查看个人调用日志"
        }}
      </h2>
      <p>
        {{
          currentUser
            ? "请在个人中心查看审批状态。"
            : "账号登录可查看自己的全部调用；使用 API Key 连接时，仅可查看该 Key 的记录。"
        }}
      </p>
      <div class="inline-actions">
        <RouterLink
          :to="currentUser ? '/account' : '/login'"
          class="button primary"
          >{{ currentUser ? "个人中心" : "账号登录" }}</RouterLink><button
          v-if="!currentUser"
          class="button"
          @click="keyDialogOpen = true"
        >
          使用 API Key
        </button>
      </div>
    </div>
    <template v-else
      ><div class="stat-grid call-log-stats">
        <div v-for="item in stats" :key="item.label" class="panel stat-card">
          <div>{{ item.label }}</div>
          <strong>{{ item.value ?? "—" }}</strong>
          <p v-if="item.label === '失败调用' && data?.summary.partial">
            另有 {{ data.summary.partial }} 次部分成功
          </p>
          <p v-else>
            {{
              item.label === "平均耗时"
                ? "服务端处理与返回耗时"
                : "按当前筛选条件统计"
            }}
          </p>
        </div>
      </div>
      <form class="panel call-log-filters" @submit.prevent="apply">
        <div class="call-log-search">
          <Search :size="17" /><input
            v-model="draft.query"
            aria-label="搜索调用日志"
            maxlength="120"
            placeholder="搜索关键词、文档标题或错误信息…"
          /><button class="button primary" :disabled="loading">查询</button
          ><button type="button" class="button" @click="reset">重置</button>
        </div>
        <div class="call-log-filter-grid">
          <label class="field"
            >调用类型<select v-model="draft.operation" @change="apply">
              <option value="">全部类型</option>
              <option
                v-for="(label, value) in operations"
                :key="value"
                :value="value"
              >
                {{ label }}
              </option>
            </select></label
          ><label class="field"
            >调用来源<select v-model="draft.client" @change="apply">
              <option value="">全部来源</option>
              <option
                v-for="(label, value) in clients"
                :key="value"
                :value="value"
              >
                {{ label }}
              </option>
            </select></label
          ><label class="field"
            >调用状态<select v-model="draft.outcome" @change="apply">
              <option value="">全部状态</option>
              <option
                v-for="(label, value) in outcomes"
                :key="value"
                :value="value"
              >
                {{ label }}
              </option>
            </select></label
          ><label class="field"
            >使用 Key<select v-model="draft.key_prefix" @change="apply">
              <option value="">全部凭据</option>
              <option v-for="key in data?.keys || []" :key="key" :value="key">
                {{ key }}
              </option>
            </select></label
          ><label class="field"
            >开始日期<input
              v-model="draft.from"
              type="date"
              @change="apply" /></label
          ><label class="field"
            >结束日期<input v-model="draft.to" type="date" @change="apply"
          /></label>
        </div>
      </form>
      <div class="panel call-log-list">
        <div class="section-heading">
          <h2>
            <Activity :size="19" />调用记录<span class="badge"
              >{{ data?.total ?? "—" }} 条</span
            >
          </h2>
          <span class="hint"
            >{{
              data?.scope === "key" ? "当前 Key 的调用" : "当前账号的调用"
            }}
            · 由新到旧</span
          >
        </div>
        <AsyncState
          :loading="loading"
          :error="error"
          :empty="!data?.logs.length"
          title="没有找到调用记录"
          description="试试调整筛选，或在工作台、MCP、CLI 发起一次知识调用后刷新。"
          @retry="reload"
          ><div class="table-scroll call-log-desktop">
            <table class="call-log-table">
              <thead>
                <tr>
                  <th>时间 / 类型</th>
                  <th>来源 / 凭据</th>
                  <th>请求与结果摘要</th>
                  <th>状态</th>
                  <th>耗时</th>
                  <th class="align-right">详情</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="log in data.logs" :key="log.id">
                  <td>
                    <strong>{{
                      operations[log.operation] || log.operation
                    }}</strong><span class="table-secondary">{{
                      formatTime(log.ts)
                    }}</span>
                  </td>
                  <td>
                    {{ clients[log.client] || log.client
                    }}<span class="table-secondary">{{
                      log.credential_kind === "session"
                        ? "网页会话"
                        : `${log.credential_name || "Key"} · ${log.key_prefix}`
                    }}</span>
                  </td>
                  <td class="call-log-summary">
                    <strong>{{ log.request_summary }}</strong><span
                      class="table-secondary"
                      >{{ log.result_summary }}</span
                    ><span v-if="log.response_truncated" class="badge"
                      >结果已截断</span
                    >
                  </td>
                  <td>
                    <span :class="['call-outcome', log.outcome]">{{
                      outcomes[log.outcome]
                    }}</span><span class="table-secondary"
                      >HTTP {{ log.status_code }}</span
                    >
                  </td>
                  <td class="call-log-duration">
                    {{ formatDuration(log.duration_ms) }}
                  </td>
                  <td class="align-right">
                    <button
                      class="button small"
                      :aria-label="`查看调用 ${log.id} 详情`"
                      @click="selected = log.id"
                    >
                      查看<ArrowUpRight :size="13" />
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="call-log-cards">
            <article
              v-for="log in data.logs"
              :key="log.id"
              class="call-log-card"
            >
              <div>
                <strong>{{
                  operations[log.operation] || log.operation
                }}</strong><span :class="['call-outcome', log.outcome]">{{
                  outcomes[log.outcome]
                }}</span>
              </div>
              <p class="call-log-card-request">{{ log.request_summary }}</p>
              <p>{{ log.result_summary }}</p>
              <small
                >{{ formatTime(log.ts) }} · {{ clients[log.client] }} ·
                {{ formatDuration(log.duration_ms) }}</small
              >
              <div class="call-log-card-bottom">
                <span>{{
                  log.credential_kind === "session"
                    ? "网页会话"
                    : log.key_prefix
                }}</span><button
                  class="text-link"
                  :aria-label="`查看调用 ${log.id} 详情`"
                  @click="selected = log.id"
                >
                  查看详情<ArrowUpRight :size="13" />
                </button>
              </div>
            </article></div
        ></AsyncState>
        <div v-if="data?.total" class="call-log-pagination">
          <span>共 {{ data.total }} 条 · 第 {{ page }} / {{ pages }} 页</span
          ><label
            >每页<select
              v-model.number="pageSize"
              aria-label="每页日志条数"
              @change="resize"
            >
              <option :value="10">10</option>
              <option :value="20">20</option>
              <option :value="50">50</option></select
            >条</label
          ><button
            class="button small"
            aria-label="上一页日志"
            :disabled="page <= 1 || loading"
            @click="page--"
          >
            <ChevronLeft :size="15" /></button
          ><button
            class="button small"
            aria-label="下一页日志"
            :disabled="page >= pages || loading"
            @click="page++"
          >
            <ChevronRight :size="15" />
          </button>
        </div>
      </div>
      <p class="hint call-log-policy">
        默认保留最近 {{ data?.retention_days ?? 30 }} 天、每个账号最多
        {{ data?.max_entries ?? 2000 }}
        条。新版本起记录请求与结果；敏感字段会隐藏，超长内容会截断并标记。查看日志不会再次生成调用记录。
      </p></template
    ><CallLogDetail
      v-if="selected !== null"
      :id="selected"
      @close="selected = null"
    />
  </section>
</template>
