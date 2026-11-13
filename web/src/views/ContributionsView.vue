<script setup>
import { ref, computed, watch, nextTick } from "vue";
import { useRoute } from "vue-router";
import { api, post } from "../services/api";
import { useResource } from "../composables/useResource";
import { notify, refreshStats, authVersion } from "../composables/workspace";
import {
  Files,
  Inbox,
  ChevronLeft,
  Check,
  MessageSquare,
  RefreshCw,
  Clock3,
  LoaderCircle,
  ArrowUpRight,
} from "lucide-vue-next";
import { plainText, relativeDate } from "../utils/format";
import MarkdownContent from "../components/MarkdownContent.vue";
import AsyncState from "../components/AsyncState.vue";
const route = useRoute(),
  review = computed(() => route.path === "/review"),
  status = ref(route.path === "/review" ? "pending" : ""),
  page = ref(1),
  selected = ref(null),
  note = ref(""),
  busy = ref(false),
  detailError = ref(""),
  detailLoading = ref(false),
  detailRoot = ref(null),
  noteInput = ref(null);
let detailSequence = 0,
  previousCard;
const labels = {
  draft: "草稿",
  pending: "待审核",
  published: "已发布",
  changes_requested: "需修改",
  rejected: "已拒绝",
};
const { data, loading, error, reload } = useResource(
  () =>
    api(
      "/contributions?" +
        new URLSearchParams({
          review: review.value,
          status: status.value,
          page: page.value,
        }),
    ),
  [review, status, page],
);
watch([review, status, page, authVersion], () => {
  detailSequence++;
  selected.value = null;
  detailError.value = "";
  detailLoading.value = false;
});
async function open(item) {
  const sequence = ++detailSequence;
  previousCard = document.activeElement;
  selected.value = null;
  detailError.value = "";
  detailLoading.value = true;
  try {
    const out = await api("/contributions/" + item.id);
    if (sequence !== detailSequence) return;
    selected.value = out;
    note.value = "";
    await nextTick();
    if (window.innerWidth <= 700) {
      detailRoot.value?.scrollIntoView({ block: "start" });
      detailRoot.value?.focus({ preventScroll: true });
    }
  } catch (e) {
    if (sequence === detailSequence) detailError.value = e.message;
  } finally {
    if (sequence === detailSequence) detailLoading.value = false;
  }
}
function closeDetail() {
  detailSequence++;
  selected.value = null;
  detailError.value = "";
  detailLoading.value = false;
  nextTick(() => previousCard?.focus());
}
async function decide(action) {
  if (action !== "publish" && !note.value.trim()) {
    notify("请填写审核意见，让贡献者知道需要如何改进。", "error");
    noteInput.value?.focus();
    return;
  }
  busy.value = true;
  try {
    selected.value = await post(
      "/contributions/" + selected.value.id + "/review",
      { action, note: note.value },
    );
    notify("审核操作已保存");
    refreshStats().catch(() => {});
    await reload();
  } catch (e) {
    notify(e.message, "error");
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <section>
    <div class="page-heading">
      <div>
        <div class="eyebrow section-eyebrow">KNOWLEDGE CONTRIBUTIONS</div>
        <h1>{{ review ? "贡献审核" : "我的贡献" }}</h1>
        <p>
          {{
            review
              ? "检查内容质量、重复项与验证证据，再决定发布或退回修改。"
              : "查看草稿、审核进度和管理员反馈。"
          }}
        </p>
      </div>
      <RouterLink to="/contribute" class="button primary">新增知识</RouterLink>
    </div>
    <div class="contribution-toolbar">
      <div class="contribution-tabs" aria-label="贡献状态筛选">
        <button
          :class="{ active: status === '' }"
          :aria-pressed="status === ''"
          @click="
            status = '';
            page = 1;
          "
        >
          全部</button
        ><button
          v-for="(name, value) in labels"
          :key="value"
          :class="{ active: status === value }"
          :aria-pressed="status === value"
          @click="
            status = value;
            page = 1;
          "
        >
          {{ name
          }}<small v-if="status === value">{{ data?.total ?? "—" }}</small>
        </button>
      </div>
      <button class="button small" :disabled="loading" @click="reload">
        <RefreshCw :size="13" :class="{ spin: loading }" />刷新
      </button>
    </div>
    <AsyncState :loading="loading" :error="error" @retry="reload"
      ><div
        :class="[
          'kb-review-layout',
          'contributions-layout',
          { 'has-selection': selected || detailLoading },
        ]"
      >
        <div>
          <button
            v-for="item in data?.items"
            :key="item.id"
            class="panel kb-contribution"
            :class="{ active: selected?.id === item.id }"
            @click="open(item)"
          >
            <span class="badge status-badge" :data-status="item.status">{{
              labels[item.status]
            }}</span>
            <h3>{{ item.title }}</h3>
            <p>
              {{
                plainText(item.summary) ||
                "点击查看知识正文、验证材料和审核记录"
              }}
            </p>
            <small
              >{{ item.source === "agent" ? "Agent 自动沉淀" : "成员贡献" }} ·
              {{ relativeDate(item.updated_at) }}</small
            >
          </button>
          <div v-if="!data?.total" class="contribution-empty">
            <Inbox :size="29" />
            <h3>
              {{
                review ? "待审核的贡献都处理完了" : "你的第一份分享，从这里开始"
              }}
            </h3>
            <p>
              {{
                review
                  ? "新的经验到来时，会出现在这里。"
                  : "记录一个值得复用的解决方案，让团队少走弯路。"
              }}
            </p>
            <RouterLink v-if="!review" to="/contribute" class="button primary"
              >开始贡献</RouterLink
            >
          </div>
          <div class="kb-pagination">
            <button class="button" :disabled="page <= 1" @click="page--">
              上一页</button
            ><span
              >{{ page }} /
              {{ Math.max(1, Math.ceil((data?.total || 0) / 20)) }}</span
            ><button
              class="button"
              :disabled="page * 20 >= (data?.total || 0)"
              @click="page++"
            >
              下一页
            </button>
          </div>
        </div>
        <article
          ref="detailRoot"
          class="panel kb-review-detail contribution-detail"
          tabindex="-1"
        >
          <button
            v-if="selected || detailLoading"
            class="text-link review-mobile-back"
            @click="closeDetail"
          >
            <ChevronLeft :size="15" />返回贡献列表
          </button>
          <div v-if="detailLoading" class="async-state" role="status">
            <LoaderCircle class="spin" :size="24" />正在加载贡献详情…
          </div>
          <p v-if="detailError" class="error-text">{{ detailError }}</p>
          <template v-if="selected"
            ><div class="section-heading">
              <h2>{{ selected.title }}</h2>
              <span class="badge status-badge" :data-status="selected.status">{{
                labels[selected.status]
              }}</span>
            </div>
            <p v-if="selected.target_doc_id" class="hint">
              更新建议 · 基于版本 {{ selected.base_version }}
              <RouterLink
                :to="{
                  name: 'document',
                  params: { id: selected.target_doc_id },
                }"
                >查看原文 →</RouterLink
              >
            </p>
            <div v-if="selected.similar.length" class="kb-callout">
              <strong>相似知识</strong>
              <p v-for="s in selected.similar" :key="s.id">
                <RouterLink :to="{ name: 'document', params: { id: s.id } }">{{
                  s.title
                }}</RouterLink>
                · {{ Math.round(s.similarity * 100) }}%
              </p>
            </div>
            <div class="review-content">
              <MarkdownContent :content="selected.content" />
            </div>
            <div
              v-if="
                selected.source === 'agent' ||
                selected.payload.problem ||
                selected.payload.verification
              "
              class="kb-callout"
            >
              <h3>验证材料</h3>
              <p
                v-for="field in [
                  'problem',
                  'solution',
                  'verification',
                  'limitations',
                ]"
                :key="field"
              >
                <strong
                  >{{
                    {
                      problem: "问题",
                      solution: "方案",
                      verification: "验证",
                      limitations: "限制",
                    }[field]
                  }}：</strong
                >{{ selected.payload[field] }}
              </p>
              <span class="badge">{{
                selected.quality.eligible ? "完整性检查通过" : "材料待完善"
              }}</span>
            </div>
            <div v-if="selected.review_note" class="kb-callout">
              <strong>审核意见</strong>
              <p>{{ selected.review_note }}</p>
            </div>
            <RouterLink
              v-if="
                !review &&
                ['draft', 'changes_requested'].includes(selected.status)
              "
              :to="{ path: '/contribute', query: { edit: selected.id } }"
              class="button primary"
              >继续编辑</RouterLink
            ><RouterLink
              v-if="selected.published_doc_id"
              :to="{
                name: 'document',
                params: { id: selected.published_doc_id },
              }"
              class="button"
              >阅读已发布知识 →</RouterLink
            >
            <form
              v-if="review && selected.status === 'pending'"
              @submit.prevent="decide('publish')"
            >
              <label class="field"
                >审核意见<textarea
                  ref="noteInput"
                  v-model="note"
                  rows="3"
                  maxlength="4000"
                  placeholder="说明发布理由或需要补充的内容"
                />
              </label>
              <div class="kb-actions">
                <button class="button primary" :disabled="busy">
                  审核并发布</button
                ><button
                  class="button"
                  type="button"
                  :disabled="busy"
                  @click="decide('changes_requested')"
                >
                  退回修改</button
                ><button
                  class="button danger"
                  type="button"
                  :disabled="busy"
                  @click="decide('reject')"
                >
                  拒绝
                </button>
              </div>
            </form>
            <h3 class="kb-history-title">操作记录</h3>
            <p v-for="event in selected.events" :key="event.id" class="hint">
              {{ new Date(event.created_at * 1000).toLocaleString() }} ·
              {{ event.actor }} ·
              {{
                {
                  save: "保存草稿",
                  submit: "提交审核",
                  publish: "发布",
                  changes_requested: "退回修改",
                  reject: "拒绝",
                }[event.action] || event.action
              }}
              {{ event.note }}
            </p></template
          >
          <div
            v-else-if="!detailLoading && !detailError"
            class="review-placeholder"
          >
            <span><Files :size="30" /></span>
            <h3>
              {{
                review
                  ? "让好的经验，被更多人看见"
                  : "每一次分享，都在积累团队的可能"
              }}
            </h3>
            <p>选择左侧的一份贡献，查看完整内容与审核进度。</p>
            <div>
              <Check :size="13" />验证方案 <span />
              <MessageSquare :size="13" />交流反馈 <span />
              <ArrowUpRight :size="13" />分享知识
            </div>
          </div>
        </article>
      </div></AsyncState
    >
  </section>
</template>
