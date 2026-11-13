<script setup>
import { ask } from "../composables/confirmation";
import { reactive, ref } from "vue";
import { api } from "../services/api";
import { useResource } from "../composables/useResource";
import { notify } from "../composables/workspace";
import AsyncState from "../components/AsyncState.vue";
const { data, loading, error, reload } = useResource(() => api("/categories"));
const form = reactive({ id: "", name: "", parent_id: "" }),
  busy = ref(false);
async function save() {
  busy.value = true;
  try {
    await api("/categories" + (form.id ? "/" + form.id : ""), {
      method: form.id ? "PUT" : "POST",
      body: { name: form.name, parent_id: form.parent_id || null },
    });
    Object.assign(form, { id: "", name: "", parent_id: "" });
    notify("分类已保存");
    reload();
  } catch (e) {
    notify(e.message, "error");
  } finally {
    busy.value = false;
  }
}
async function remove(c) {
  if (!(await ask("删除空分类“" + c.name + "”？"))) return;
  try {
    await api("/categories/" + c.id, { method: "DELETE" });
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
        <div class="eyebrow section-eyebrow">TAXONOMY</div>
        <h1>分类管理</h1>
        <p>管理员可以创建分类、调整层级。知识可通过更新建议移动到其他分类。</p>
      </div>
    </div>
    <AsyncState :loading="loading" :error="error" @retry="reload"
      ><div class="kb-review-layout">
        <div class="panel kb-review-detail">
          <div
            v-for="c in data?.categories"
            :key="c.id"
            class="kb-category-row"
          >
            <div>
              <strong>{{ c.path }}</strong><small
                >{{ c.documents }} 篇 · {{ c.id }}</small
              >
            </div>
            <button class="button small" @click="Object.assign(form, c)">
              编辑</button
            ><button class="text-link" @click="remove(c)">删除</button>
          </div>
        </div>
        <form class="panel kb-review-detail" @submit.prevent="save">
          <h2>{{ form.id ? "编辑分类" : "新增分类" }}</h2>
          <label class="field"
            >名称<input v-model="form.name" required maxlength="60" /></label
          ><label class="field"
            >上级分类<select v-model="form.parent_id">
              <option value="">顶级分类</option>
              <option
                v-for="c in data?.categories?.filter((c) => c.id !== form.id)"
                :key="c.id"
                :value="c.id"
              >
                {{ c.path }}
              </option>
            </select></label
          >
          <div class="kb-actions">
            <button class="button primary" :disabled="busy">保存</button
            ><button
              class="button"
              type="button"
              @click="Object.assign(form, { id: '', name: '', parent_id: '' })"
            >
              重置
            </button>
          </div>
        </form>
      </div></AsyncState
    >
  </section>
</template>
