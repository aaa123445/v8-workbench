<script setup>
import { ask } from "../composables/confirmation";
import { computed, reactive, ref } from "vue";
import { UsersRound, RefreshCw } from "lucide-vue-next";
import { api } from "../services/api";
import { notify } from "../composables/workspace";
import { statusLabel, roleLabel } from "../composables/session";
import { useResource } from "../composables/useResource";
import AsyncState from "./AsyncState.vue";
const drafts = reactive({}),
  filter = ref("pending"),
  saving = ref("");
const { data, loading, error, reload } = useResource(async () => {
  const data = await api("/admin/users");
  for (const user of data.users)
    drafts[user.id] = {
      role: user.status === "pending" ? "writer" : user.role,
      note: user.review_note || "",
    };
  return data;
});
const users = computed(() =>
  (data.value?.users || []).filter(
    (u) => !filter.value || u.status === filter.value,
  ),
);
const pending = computed(
  () => (data.value?.users || []).filter((u) => u.status === "pending").length,
);
async function review(user, status) {
  if (
    (status === "disabled" || status === "rejected") &&
    !(await ask(
      `确认${statusLabel(status)}账号「${user.display_name}」？此账号的 Key 会被吊销。`,
    ))
  )
    return;
  if (
    drafts[user.id].role === "admin" &&
    !(await ask(
      "此角色可以审批账号、管理全部 Key 和知识库，确认授予管理员权限？",
    ))
  )
    return;
  saving.value = user.id;
  try {
    await api("/admin/users/" + user.id, {
      method: "PATCH",
      body: { status, ...drafts[user.id] },
    });
    notify("账号状态已更新");
    await reload();
  } catch (e) {
    notify(e.message, "error");
  } finally {
    saving.value = "";
  }
}
</script>
<template>
  <div class="panel account-approvals">
    <div class="section-heading">
      <h2>
        <UsersRound :size="20" />账号审批与管理<span class="badge"
          >待审批 {{ pending }}</span
        >
      </h2>
      <button class="icon-button" aria-label="刷新账号列表" @click="reload">
        <RefreshCw :size="16" />
      </button>
    </div>
    <p class="muted">
      注册账号默认无法使用工作台。核实身份后分配角色并批准入网；停用或拒绝会吊销该账号全部
      Key。
    </p>
    <div class="filter-row">
      <button
        v-for="[value, label] in [
          ['pending', '待审批'],
          ['approved', '已入网'],
          ['rejected', '未通过'],
          ['disabled', '已停用'],
          ['', '全部账号'],
        ]"
        :key="value"
        :class="['chip', { active: filter === value }]"
        @click="filter = value"
      >
        {{ label }}
      </button>
    </div>
    <AsyncState
      :loading="loading"
      :error="error"
      :empty="!users.length"
      title="当前分类没有账号"
      @retry="reload"
      ><div v-for="user in users" :key="user.id" class="approval-card">
        <div class="approval-card-heading">
          <div>
            <strong>{{ user.display_name }}</strong><span
              >@{{ user.username }}</span
            >
          </div>
          <span :class="['badge', { green: user.status === 'approved' }]">{{
            statusLabel(user.status)
          }}</span><small
            >{{
              new Date(user.created_at * 1000).toLocaleDateString("zh-CN")
            }}
            注册</small
          >
        </div>
        <div class="approval-controls">
          <label class="field"
            >账号权限<select
              v-model="drafts[user.id].role"
              :aria-label="`账号权限 ${user.username}`"
            >
              <option value="reader">只读成员 · reader</option>
              <option value="writer">读写成员 · writer</option>
              <option value="admin">管理员 · admin</option>
            </select></label
          ><label class="field"
            >审批说明<input
              v-model="drafts[user.id].note"
              :aria-label="`审批说明 ${user.username}`"
              maxlength="500"
              placeholder="选填，用户可在个人中心查看"
          /></label>
        </div>
        <div class="approval-actions">
          <button
            class="button primary small"
            :disabled="!!saving"
            @click="review(user, 'approved')"
          >
            {{
              user.status === "approved" ? "保存权限" : "批准入网"
            }}</button><button
            v-if="user.status === 'pending'"
            class="button small danger"
            :disabled="!!saving"
            @click="review(user, 'rejected')"
          >
            拒绝申请</button
          ><button
            v-if="user.status === 'approved'"
            class="button small danger"
            :disabled="!!saving"
            @click="review(user, 'disabled')"
          >
            停用账号
          </button>
        </div>
      </div></AsyncState
    >
  </div>
</template>
