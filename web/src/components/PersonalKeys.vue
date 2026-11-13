<script setup>
import { ask } from "../composables/confirmation";
import { useRouter } from "vue-router";
import { handoffConnectionKey } from "../composables/connection";
import { computed, ref } from "vue";
import { KeyRound, Copy, Plus, Trash2, LoaderCircle } from "lucide-vue-next";
import { api, post } from "../services/api";
import { currentUser } from "../composables/session";
import { notify } from "../composables/workspace";
import { useResource } from "../composables/useResource";
import AsyncState from "./AsyncState.vue";
const router = useRouter();
function connect() {
  handoffConnectionKey(newKey.value);
  newKey.value = "";
  router.push("/connect");
}
const { data, loading, error, reload } = useResource(() =>
  api("/account/keys", { key: "" }),
);
const name = ref(""),
  role = ref("reader"),
  busy = ref(false),
  revoking = ref(""),
  newKey = ref("");
const ranks = { reader: 1, writer: 2, admin: 3 };
const roles = computed(() =>
  Object.keys(ranks).filter(
    (role) => ranks[role] <= ranks[currentUser.value?.role],
  ),
);
async function create() {
  busy.value = true;
  try {
    const result = await post(
      "/account/keys",
      { name: name.value.trim(), role: role.value },
      { key: "" },
    );
    newKey.value = result.key;
    name.value = "";
    notify("个人 Key 已创建，请立即复制保存");
    await reload();
  } catch (e) {
    notify(e.message, "error");
  } finally {
    busy.value = false;
  }
}
async function revoke(key) {
  if (
    !(await ask(
      `确认吊销「${key.name}」？使用此 Key 的 MCP、Skill 或 CLI 将无法继续访问。`,
    ))
  )
    return;
  revoking.value = key.key_prefix;
  try {
    await api("/account/keys/" + encodeURIComponent(key.key_prefix), {
      key: "",
      method: "DELETE",
    });
    notify("个人 Key 已吊销");
    await reload();
  } catch (e) {
    notify(e.message, "error");
  } finally {
    revoking.value = "";
  }
}
async function copy() {
  try {
    await navigator.clipboard.writeText(newKey.value);
    notify("已复制个人 Key");
  } catch {
    notify("复制失败，请手动选择并保存", "error");
  }
}
</script>
<template>
  <div class="panel">
    <div class="section-heading">
      <h2><KeyRound :size="19" />我的 API Key</h2>
      <RouterLink to="/connect" class="text-link"
        >一键接入 MCP / Skill / CLI →</RouterLink
      >
    </div>
    <p class="muted">
      仅显示当前账号的 Key。按客户端分别创建，最多启用 20
      个，权限不超过账号角色。
    </p>
    <div v-if="newKey" class="new-key-box" role="status">
      <strong>仅显示这一次，请立即保存</strong>
      <div>
        <code>{{ newKey }}</code><button class="button small" @click="copy">
          <Copy :size="14" />复制
        </button>
      </div>
      <button class="text-link" @click="newKey = ''">已保存，关闭显示</button>
      <button class="button small" @click="connect">
        用此 Key 生成安装提示词 →
      </button>
    </div>
    <AsyncState :loading="loading" :error="error" @retry="reload"
      ><div v-if="data?.keys?.length" class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>名称 / 前缀</th>
              <th>权限</th>
              <th>今日调用</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="key in data.keys" :key="key.key_prefix">
              <td>
                <strong>{{ key.name }}</strong><code class="table-secondary">{{
                  key.key_prefix
                }}</code>
              </td>
              <td>
                <span class="badge">{{ key.role }}</span>
              </td>
              <td>{{ key.used_today }} / {{ key.daily_limit }}</td>
              <td>
                <span :class="['badge', { green: key.enabled }]">{{
                  key.enabled ? "启用" : "已吊销"
                }}</span>
              </td>
              <td>
                <button
                  v-if="key.enabled"
                  class="button small danger"
                  :disabled="!!revoking"
                  @click="revoke(key)"
                >
                  <Trash2 :size="13" />吊销
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="personal-empty">
        <KeyRound :size="27" />
        <h3>创建第一个个人 Key</h3>
        <p>为本机 Agent 或命令行单独创建访问凭据。</p>
      </div></AsyncState
    >
    <form class="create-key-form" @submit.prevent="create">
      <label class="field"
        >Key 名称<input
          v-model="name"
          required
          maxlength="80"
          placeholder="例如：我的 Codex / 办公电脑 CLI" /></label
      ><label class="field"
        >Key 权限<select v-model="role">
          <option v-for="item in roles" :key="item" :value="item">
            {{ item }}
          </option>
        </select></label
      ><button class="button primary" :disabled="busy || !name.trim()">
        <LoaderCircle v-if="busy" class="spin" :size="16" /><Plus
          v-else
          :size="16"
        />创建个人 Key
      </button>
    </form>
    <p class="hint">
      只查询文档选 reader；需要提交经验选
      writer。吊销后无法恢复，需要重新创建并更新客户端配置。
    </p>
  </div>
</template>
