<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import {
  UserRound,
  ShieldCheck,
  Clock3,
  RefreshCw,
  LockKeyhole,
  Activity,
} from "lucide-vue-next";
import {
  currentUser,
  statusLabel,
  roleLabel,
  refreshUser,
  passwordChanged,
} from "../composables/session";
import { notify, keyDialogOpen } from "../composables/workspace";
import { post } from "../services/api";
import PersonalKeys from "../components/PersonalKeys.vue";
const router = useRouter(),
  busy = ref(false),
  passwordBusy = ref(false),
  current = ref(""),
  newPassword = ref(""),
  confirmation = ref(""),
  error = ref("");
async function refresh() {
  busy.value = true;
  try {
    await refreshUser();
    notify("审批状态已更新");
  } catch (e) {
    if (e.status === 401) {
      currentUser.value = null;
      router.push("/login");
    } else notify(e.message, "error");
  } finally {
    busy.value = false;
  }
}
async function changePassword() {
  error.value = "";
  if (newPassword.value !== confirmation.value) {
    error.value = "两次输入的新密码不一致";
    return;
  }
  passwordBusy.value = true;
  try {
    await post(
      "/auth/password",
      { current_password: current.value, new_password: newPassword.value },
      { key: "" },
    );
    passwordChanged();
    notify("密码已修改，请重新登录");
    router.push("/login");
  } catch (e) {
    error.value = e.message;
  } finally {
    passwordBusy.value = false;
  }
}
</script>
<template>
  <section class="account-page">
    <div class="page-heading">
      <div>
        <div class="eyebrow section-eyebrow">YOUR ACCOUNT, YOUR ACCESS</div>
        <h1>个人中心</h1>
        <p>查看入网状态，管理只属于你的客户端访问凭据。</p>
      </div>
      <RouterLink to="/account/logs" class="button"
        ><Activity :size="16" />我的调用日志</RouterLink
      >
    </div>
    <div v-if="!currentUser" class="panel account-login-prompt">
      <UserRound :size="32" />
      <h2>使用账号管理个人 Key</h2>
      <p>
        已有 API Key 可继续访问知识库。个人 Key
        管理需要账号登录；原有管理员可在管理页审批账号。
      </p>
      <div class="inline-actions">
        <RouterLink to="/login" class="button primary">账号登录</RouterLink
        ><RouterLink to="/register" class="button">注册入网</RouterLink
        ><button class="button" @click="keyDialogOpen = true">
          已有管理员 Key
        </button>
      </div>
    </div>
    <template v-else
      ><div class="account-profile panel">
        <span class="account-avatar">{{
          currentUser.display_name.slice(0, 1)
        }}</span>
        <div>
          <h2>{{ currentUser.display_name }}</h2>
          <p>@{{ currentUser.username }} · {{ roleLabel(currentUser.role) }}</p>
        </div>
        <span
          :class="['badge', { green: currentUser.status === 'approved' }]"
          >{{ statusLabel(currentUser.status) }}</span><button
          class="button small"
          :disabled="busy"
          @click="refresh"
        >
          <RefreshCw :class="{ spin: busy }" :size="14" />刷新状态
        </button>
      </div>
      <div
        v-if="currentUser.status !== 'approved'"
        class="approval-state panel"
      >
        <Clock3 :size="32" />
        <h2>
          {{
            currentUser.status === "pending"
              ? "注册成功，等待管理员审批"
              : currentUser.status === "rejected"
                ? "入网申请未通过"
                : "账号已被停用"
          }}
        </h2>
        <p>
          {{
            currentUser.status === "pending"
              ? "管理员确认你的身份并分配权限后，即可访问知识库和创建个人 Key。"
              : "请联系管理员确认原因；账号恢复后可继续登录使用。"
          }}
        </p>
        <blockquote v-if="currentUser.review_note">
          管理员说明：{{ currentUser.review_note }}
        </blockquote>
        <RouterLink to="/guide" class="button">先阅读接入说明</RouterLink>
      </div>
      <PersonalKeys v-else />
      <details class="panel password-panel">
        <summary><LockKeyhole :size="17" />修改登录密码</summary>
        <form class="password-form" @submit.prevent="changePassword">
          <label class="field"
            >当前密码<input
              v-model="current"
              type="password"
              required
              autocomplete="current-password"
              maxlength="128" /></label
          ><label class="field"
            >新密码<input
              v-model="newPassword"
              type="password"
              required
              minlength="10"
              maxlength="128"
              autocomplete="new-password"
              placeholder="10–128 个字符" /></label
          ><label class="field"
            >确认新密码<input
              v-model="confirmation"
              type="password"
              required
              minlength="10"
              maxlength="128"
              autocomplete="new-password"
          /></label>
          <p class="hint">
            修改后所有浏览器会话会退出。客户端 API Key
            不自动更换，如有泄露请在上方吊销。
          </p>
          <p v-if="error" class="error-text" role="alert">{{ error }}</p>
          <button class="button primary" :disabled="passwordBusy">
            {{ passwordBusy ? "保存中…" : "修改并重新登录" }}
          </button>
        </form>
      </details></template
    >
  </section>
</template>
