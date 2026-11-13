<script setup>
import {
  reactive,
  ref,
  computed,
  onMounted,
  onBeforeUnmount,
  nextTick,
} from "vue";
import { useRoute, onBeforeRouteLeave } from "vue-router";
import { api, post } from "../services/api";
import { notify } from "../composables/workspace";
import MarkdownEditor from "../components/workspace/MarkdownEditor.vue";
import {
  FileCheck2,
  Check,
  Circle,
  ArrowRight,
  ShieldCheck,
  LoaderCircle,
} from "lucide-vue-next";
import { confirmAction } from "../composables/confirmation";
import CategorySuggestion from "../components/CategorySuggestion.vue";
const route = useRoute(),
  categories = ref([]),
  busy = ref(false),
  initializing = ref(true),
  blocked = ref(false),
  error = ref(""),
  saved = ref(null),
  latestTargetVersion = ref(null),
  id = ref(route.query.edit || "");
const form = reactive({
  title: "",
  content: "",
  category_id: "uncategorized",
  tags: "",
  summary: "",
  source: "manual",
  target_doc_id: route.query.target || "",
  base_version: null,
  problem: "",
  solution: "",
  verification: "",
  limitations: "",
  verified: false,
  reusable: false,
});
const clean = ref(JSON.stringify(form));
const dirty = computed(() => JSON.stringify(form) !== clean.value);
const checks = computed(() => [
  { name: "清晰的知识标题", done: form.title.trim().length > 0 },
  { name: "完整的解决过程", done: form.content.trim().length >= 80 },
  {
    name: "真实的验证结果",
    done: form.verified && form.verification.trim().length >= 10,
  },
  { name: "明确的适用范围", done: form.limitations.trim().length >= 5 },
]);
function keydown(e) {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
    e.preventDefault();
    if (
      !busy.value &&
      !initializing.value &&
      !blocked.value &&
      !["pending", "published", "rejected"].includes(saved.value?.status)
    )
      save(false);
  }
}
function beforeUnload(e) {
  if (dirty.value) {
    e.preventDefault();
    e.returnValue = "";
  }
}
onMounted(() => {
  window.addEventListener("keydown", keydown);
  window.addEventListener("beforeunload", beforeUnload);
});
onBeforeUnmount(() => {
  window.removeEventListener("keydown", keydown);
  window.removeEventListener("beforeunload", beforeUnload);
});
onBeforeRouteLeave(
  () =>
    JSON.stringify(form) === clean.value ||
    confirmAction({
      title: "离开编辑器？",
      message: "当前内容尚未保存，离开后将丢失这些更改。",
      confirmLabel: "放弃更改",
      danger: true,
    }),
);
onMounted(async () => {
  try {
    categories.value = (await api("/categories")).categories;
    if (id.value) {
      const d = await api("/contributions/" + encodeURIComponent(id.value));
      Object.assign(form, d.payload, { tags: d.tags.join(", ") });
      if (form.target_doc_id) {
        const latest = await post("/read", {
          id: form.target_doc_id,
          max_chars: 1,
        });
        latestTargetVersion.value = latest.knowledge_version;
      }
    } else if (form.target_doc_id) {
      let d = await post("/read", { id: form.target_doc_id });
      const initialVersion = d.knowledge_version;
      let body = d.content;
      while (d.truncated && body.length <= 200000) {
        d = await post("/read", {
          id: form.target_doc_id,
          offset: d.next_offset,
        });
        if (d.knowledge_version !== initialVersion)
          throw new Error("原文在加载时已变化，请刷新后重试。");
        body += d.content;
      }
      if (body.length > 200000)
        throw new Error(
          "原文超过更新建议的长度限制，请创建补充知识并引用原文。",
        );
      Object.assign(form, {
        title: d.title,
        content: body,
        category_id: d.category_id,
        base_version: d.knowledge_version,
        tags: d.tags.join(", "),
      });
    }
  } catch (e) {
    error.value = e.message;
    blocked.value = true;
  } finally {
    initializing.value = false;
    clean.value = JSON.stringify(form);
  }
});
async function save(submit) {
  if (initializing.value || blocked.value || busy.value) return;
  if (!form.title.trim() || form.content.trim().length < 20) {
    error.value = "请填写知识标题，正文至少需要 20 个字符。";
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    const payload = {
      ...form,
      tags: form.tags
        .split(/[,，]/)
        .map((x) => x.trim())
        .filter(Boolean),
    };
    saved.value = await api(
      "/contributions" +
        (id.value ? "/" + encodeURIComponent(id.value) : "") +
        "?submit=" +
        submit,
      { method: id.value ? "PUT" : "POST", body: payload },
    );
    if (saved.value.id) id.value = saved.value.id;
    clean.value = JSON.stringify(form);
    notify(submit ? "已提交审核，发布后团队可检索" : "草稿已保存");
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
async function template() {
  if (
    form.content &&
    !(await confirmAction({
      title: "使用经验模板？",
      message: "这会替换当前正文，建议先保存草稿。",
      confirmLabel: "使用模板",
    }))
  )
    return;
  form.content =
    "## 问题与背景\n\n## 原因分析\n\n## 解决步骤\n\n## 验证结果\n\n## 适用范围与限制\n";
}
</script>
<template>
  <section>
    <div class="page-heading">
      <div>
        <div class="eyebrow section-eyebrow">CONTRIBUTE & IMPROVE</div>
        <h1>
          {{ form.target_doc_id ? "建议更新知识" : "让经验成为团队的资产" }}
        </h1>
        <p>草稿仅自己可见，提交后由管理员审核，发布后进入团队知识库。</p>
      </div>
      <RouterLink to="/contributions" class="button">我的贡献 →</RouterLink>
    </div>
    <div v-if="saved" class="success-banner" role="status">
      {{
        saved.status === "draft"
          ? "草稿已保存"
          : saved.status === "duplicate"
            ? "发现相同知识，请复用现有文档"
            : "已提交审核"
      }}
      <RouterLink
        :to="
          saved.status === 'duplicate'
            ? { name: 'document', params: { id: saved.duplicate.id } }
            : '/contributions'
        "
        >查看 →</RouterLink
      >
    </div>
    <div class="contribute-layout">
      <form
        class="panel contribute-form studio-editor-form"
        @submit.prevent="save(true)"
      >
        <div class="editor-form-heading">
          <span class="editor-step">01</span>
          <div>
            <h2>{{ id ? "编辑贡献" : "写下一份值得分享的知识" }}</h2>
            <p>让读到它的人，少走一次弯路。</p>
          </div>
          <span :class="['save-status', { dirty }]"
            ><i />{{ dirty ? "尚未保存" : id ? "已保存" : "新知识" }}</span
          >
        </div>
        <label class="field"
          >知识标题 *<input
            v-model="form.title"
            required
            maxlength="300"
            placeholder="例如：反向代理后客户端 IP 获取异常的解决方案"
        /></label>
        <CategorySuggestion
          :title="form.title"
          :content="form.content"
          @select="form.category_id = $event"
        />
        <div class="form-row">
          <label class="field"
            >知识分类<select v-model="form.category_id">
              <option v-for="c in categories" :key="c.id" :value="c.id">
                {{ c.path }}
              </option>
            </select></label
          ><label class="field"
            >标签<input v-model="form.tags" placeholder="部署, Nginx, 网络"
          /></label>
        </div>
        <label class="field"
          >摘要<input
            v-model="form.summary"
            maxlength="2000"
            placeholder="一句话说明这份知识可以解决什么问题"
        /></label>
        <p v-if="form.target_doc_id" class="hint">
          更新目标：{{ form.target_doc_id }} · 审核通过前不会覆盖原文。
        </p>
        <label class="editor-section-label" for="knowledge-content"
          >知识正文 <span>*</span></label
        >
        <MarkdownEditor v-model="form.content" @template="template" />
        <details class="kb-callout" :open="form.source === 'agent'">
          <summary>
            问题、验证与适用限制{{
              form.source === "agent" ? "（Agent 必填）" : "（可选）"
            }}
          </summary>
          <label
            v-for="(label, field) in {
              problem: '问题背景',
              solution: '具体方案',
              verification: '实际验证证据',
              limitations: '适用范围与限制',
            }"
            :key="field"
            class="field"
            >{{ label
            }}<textarea
              v-model="form[field]"
              rows="3"
              :maxlength="field === 'solution' ? 20000 : 10000"
            />
          </label>
          <label
            ><input v-model="form.verified" type="checkbox" /> 已实际验证</label
          >
          ·
          <label
            ><input v-model="form.reusable" type="checkbox" />
            具备复用价值</label
          >
        </details>
        <div
          v-if="
            latestTargetVersion && latestTargetVersion !== form.base_version
          "
          class="kb-callout"
        >
          <p>
            目标文档已更新为 v{{
              latestTargetVersion
            }}。请先阅读原文，合并变更后再提交。
          </p>
          <RouterLink
            :to="{ name: 'document', params: { id: form.target_doc_id } }"
            target="_blank"
            >阅读最新文档 →</RouterLink
          ><button
            class="button small"
            type="button"
            @click="form.base_version = latestTargetVersion"
          >
            已核对并合并最新版本
          </button>
        </div>
        <p v-if="initializing" class="hint" role="status">正在载入完整内容…</p>
        <p v-if="error" class="error-text" role="alert">{{ error }}</p>
        <div class="form-submit editor-submit">
          <span class="editor-save-note"
            ><ShieldCheck :size="14" />审核通过后，团队成员可检索</span
          >
          <button
            class="button"
            type="button"
            :disabled="
              busy ||
              initializing ||
              blocked ||
              ['pending', 'published', 'rejected'].includes(saved?.status)
            "
            @click="save(false)"
          >
            <LoaderCircle v-if="busy" class="spin" :size="13" />保存草稿</button
          ><button
            class="button primary"
            :disabled="
              busy ||
              initializing ||
              blocked ||
              ['pending', 'published', 'rejected'].includes(saved?.status)
            "
          >
            {{ busy ? "保存中…" : "提交审核" }}
          </button>
        </div>
      </form>
      <aside class="contribute-tips">
        <span class="editor-aside-icon"><FileCheck2 :size="24" /></span>
        <h3>让这份知识更有价值</h3>
        <p>一份能独立阅读、被再次复用的方案，通常包含这些内容。</p>
        <div class="editor-checklist">
          <div
            v-for="check in checks"
            :key="check.name"
            :class="{ done: check.done }"
          >
            <Check v-if="check.done" :size="15" /><Circle v-else :size="14" />{{
              check.name
            }}
          </div>
        </div>
        <div class="editor-aside-divider" />
        <h3>分享前，再确认一次</h3>

        <ol>
          <li>
            <strong>先检索，避免重复</strong>
            <p>已有知识需要修正时，在文档页选择“建议更新”。</p>
          </li>
          <li>
            <strong>只记录真实结果</strong>
            <p>未经测试的推测请明确标注，不要作为验证结论。</p>
          </li>
          <li>
            <strong>提交前脱敏</strong>
            <p>删除密钥、密码、客户数据和内部连接信息。</p>
          </li>
        </ol>
        <RouterLink to="/guide" class="text-link"
          >让本地 Agent 自动沉淀 →</RouterLink
        >
      </aside>
    </div>
  </section>
</template>
