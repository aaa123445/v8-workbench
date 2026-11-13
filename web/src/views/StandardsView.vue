<script setup>
import { ask } from "../composables/confirmation";
import { ref, reactive } from "vue";
import { api } from "../services/api";
import { isAdmin } from "../composables/session";
import { notify } from "../composables/workspace";
import { useResource } from "../composables/useResource";
import MarkdownContent from "../components/MarkdownContent.vue";
import AsyncState from "../components/AsyncState.vue";
const { data, loading, error, reload } = useResource(() => api("/standards"));
const { data: cats } = useResource(() => api("/categories"));
const form = reactive({
    id: "",
    name: "",
    category_id: "standards",
    description: "",
    checklist: "",
    doc_ids: "",
  }),
  editing = ref(false),
  busy = ref(false);
function edit(r) {
  Object.assign(
    form,
    r
      ? {
          ...r,
          checklist: r.checklist.join("\n"),
          doc_ids: r.doc_ids.join("\n"),
        }
      : {
          id: "",
          name: "",
          category_id: "standards",
          description: "",
          checklist: "",
          doc_ids: "",
        },
  );
  editing.value = true;
}
async function save() {
  busy.value = true;
  try {
    await api("/standards" + (form.id ? "/" + form.id : ""), {
      method: form.id ? "PUT" : "POST",
      body: {
        ...form,
        checklist: form.checklist
          .split("\n")
          .map((x) => x.trim())
          .filter(Boolean),
        doc_ids: form.doc_ids
          .split("\n")
          .map((x) => x.trim())
          .filter(Boolean),
      },
    });
    editing.value = false;
    notify("规范已保存");
    reload();
  } catch (e) {
    notify(e.message, "error");
  } finally {
    busy.value = false;
  }
}
async function remove(r) {
  if (!(await ask("删除规范“" + r.name + "”？"))) return;
  try {
    await api("/standards/" + r.id, { method: "DELETE" });
    reload();
  } catch (e) {
    notify(e.message, "error");
  }
}
</script>
<template>
  <section>
    <div class="page-heading">
      <div>
        <div class="eyebrow section-eyebrow">TEAM STANDARDS</div>
        <h1>团队规范</h1>
        <p>
          按分类维护团队约定、执行清单和参考文档，Agent 可通过 kb_rules 获取。
        </p>
      </div>
      <button v-if="isAdmin" class="button primary" @click="edit(null)">
        新增规范
      </button>
    </div>
    <form
      v-if="editing"
      class="panel kb-review-detail kb-editor"
      @submit.prevent="save"
    >
      <h2>{{ form.id ? "编辑规范" : "新增规范" }}</h2>
      <div class="form-row">
        <label class="field"
          >规范名称<input v-model="form.name" required maxlength="120" /></label
        ><label class="field"
          >适用分类<select v-model="form.category_id">
            <option v-for="c in cats?.categories" :key="c.id" :value="c.id">
              {{ c.path }}
            </option>
          </select></label
        >
      </div>
      <label class="field"
        >规范说明<textarea v-model="form.description" rows="3" /></label
      ><label class="field"
        >检查清单（每行一项）<textarea
          v-model="form.checklist"
          rows="5"
        /></label
      ><label class="field"
        >关联文档 ID（每行一项）<textarea v-model="form.doc_ids" rows="3" />
      </label>
      <div class="kb-actions">
        <button class="button primary" :disabled="busy">保存规范</button
        ><button class="button" type="button" @click="editing = false">
          取消
        </button>
      </div>
    </form>
    <AsyncState :loading="loading" :error="error" @retry="reload"
      ><div class="kb-cards">
        <article
          v-for="r in data?.standards"
          :key="r.id"
          class="panel kb-review-detail"
        >
          <span class="badge">{{
            cats?.categories?.find((c) => c.id === r.category_id)?.name
          }}</span>
          <h2>{{ r.name }}</h2>
          <MarkdownContent :content="r.description" />
          <ul>
            <li v-for="(item, i) in r.checklist" :key="i">{{ item }}</li>
          </ul>
          <p v-for="id in r.doc_ids" :key="id">
            <RouterLink :to="{ name: 'document', params: { id } }"
              >阅读 {{ id }} →</RouterLink
            >
          </p>
          <div v-if="isAdmin" class="kb-actions">
            <button class="button small" @click="edit(r)">编辑</button
            ><button class="text-link" @click="remove(r)">删除</button>
          </div>
        </article>
      </div>
      <div v-if="!data?.standards?.length" class="panel async-state">
        尚未配置团队规范，管理员可以在这里添加。原有致远 V8 规范仍可通过
        v8_rules 工具获取。
      </div></AsyncState
    >
  </section>
</template>
