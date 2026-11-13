<script setup>
import { ref, reactive } from "vue";
import { Bot } from "lucide-vue-next";
import { api } from "../services/api";
import { notify } from "../composables/workspace";
const form = reactive({
  enabled: false,
  base_url: "",
  model: "",
  api_key: "",
  clear_key: false,
});
const status = ref(null),
  busy = ref(false),
  error = ref(""),
  loaded = ref(false);
async function load() {
  error.value = "";
  try {
    const d = await api("/admin/assistant");
    status.value = d;
    Object.assign(form, {
      enabled: d.enabled,
      base_url: d.base_url,
      model: d.model,
      api_key: "",
      clear_key: false,
    });
    loaded.value = true;
  } catch (e) {
    error.value = e.message;
  }
}
async function save() {
  busy.value = true;
  try {
    status.value = await api("/admin/assistant", { method: "PUT", body: form });
    form.api_key = "";
    form.clear_key = false;
    notify("云端智能体配置已保存");
  } catch (e) {
    notify(e.message, "error");
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <section class="panel agent-settings">
    <div class="section-heading">
      <h2><Bot :size="19" />云端智能体</h2>
      <button class="button small" @click="load">
        {{ loaded ? "刷新配置" : "配置模型服务" }}
      </button>
    </div>
    <p class="hint">
      兼容 OpenAI Chat Completions
      协议。发送当前问题、最近对话和相关已发布知识片段，不执行命令。启用前请确认该模型服务适合处理团队知识。
    </p>
    <p v-if="error" class="error-text" role="alert">{{ error }}</p>
    <form v-if="loaded" @submit.prevent="save">
      <div class="form-row">
        <label class="field"
          >API 根地址（支持 HTTP / HTTPS）<input
            v-model="form.base_url"
            placeholder="https://provider.example/v1"
            maxlength="1000" /></label
        ><label class="field"
          >模型名称<input
            v-model="form.model"
            placeholder="填写服务商提供的模型 ID"
            maxlength="150"
        /></label>
      </div>
      <label class="field"
        >模型 API Key<input
          v-model="form.api_key"
          type="password"
          autocomplete="new-password"
          :placeholder="
            status?.key_configured
              ? '已配置；留空保留原 Key'
              : '填写模型服务 API Key'
          "
          :disabled="status?.key_from_environment"
          maxlength="1000"
      /></label>
      <p v-if="status?.key_from_environment" class="hint">
        Key 由服务器环境变量提供，请在服务器更换。
      </p>
      <label class="connect-check"
        ><input v-model="form.enabled" type="checkbox" />启用云端问答</label
      ><label
        v-if="status?.key_configured && !status?.key_from_environment"
        class="connect-check"
        ><input v-model="form.clear_key" type="checkbox" />清除已保存的模型
        Key（需同时关闭云端问答）</label
      ><button class="button primary" :disabled="busy">
        {{ busy ? "保存中…" : "保存模型配置" }}</button
      ><span class="hint">
        {{
          status?.ready
            ? "当前已具备调用配置，实际连通性以问答结果为准。"
            : "当前未启用或配置不完整。"
        }}</span
      >
    </form>
  </section>
</template>
