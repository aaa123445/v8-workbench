<script setup>
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  LogIn,
  UserPlus,
  ShieldCheck,
  KeyRound,
  LoaderCircle,
} from "lucide-vue-next";
import { post } from "../services/api";
import { login, currentUser } from "../composables/session";
import { keyDialogOpen } from "../composables/workspace";
const route = useRoute(),
  router = useRouter();
const registering = computed(() => route.path === "/register");
const username = ref(""),
  displayName = ref(""),
  password = ref(""),
  confirmation = ref(""),
  error = ref(""),
  busy = ref(false);
watch(registering, () => {
  error.value = "";
  password.value = "";
  confirmation.value = "";
});
async function submit() {
  error.value = "";
  if (registering.value && password.value !== confirmation.value) {
    error.value = "两次输入的密码不一致";
    return;
  }
  busy.value = true;
  try {
    if (registering.value)
      await post(
        "/auth/register",
        {
          username: username.value,
          display_name: displayName.value,
          password: password.value,
        },
        { key: "" },
      );
    await login(username.value, password.value);
    password.value = "";
    confirmation.value = "";
    router.replace("/account");
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <section class="auth-layout">
    <div class="auth-story">
      <span class="eyebrow section-eyebrow">YOUR TEAM, YOUR KNOWLEDGE</span>
      <h1>从一个账号开始，<br />连接团队的知识。</h1>
      <p>
        查询平台文档、获取开发规范、沉淀实践经验，<br />为你的 Agent
        创建专属访问凭据。
      </p>
      <div class="auth-steps">
        <div>
          <span>01</span><strong>注册账号</strong
          ><small>填写用户名与姓名</small>
        </div>
        <div>
          <span>02</span><strong>管理员审批</strong
          ><small>分配角色，批准入网</small>
        </div>
        <div>
          <span>03</span><strong>连接工作空间</strong
          ><small>登录使用，按需创建个人 Key</small>
        </div>
      </div>
      <RouterLink to="/guide" class="text-link"
        >先了解 MCP / Skill / CLI 的接入方式 →</RouterLink
      >
    </div>
    <div class="panel auth-form">
      <template v-if="currentUser"
        ><ShieldCheck class="auth-symbol" :size="30" />
        <h2>你已登录</h2>
        <p class="muted">当前账号：{{ currentUser.display_name }}</p>
        <RouterLink to="/account" class="button primary wide"
          >进入个人中心</RouterLink
        ></template
      ><template v-else
        ><div class="auth-tabs">
          <RouterLink to="/login" :class="{ active: !registering }"
            >账号登录</RouterLink
          ><RouterLink to="/register" :class="{ active: registering }"
            >注册入网</RouterLink
          >
        </div>
        <h2>{{ registering ? "创建你的工作台账号" : "欢迎回到工作台" }}</h2>
        <p class="muted">
          {{
            registering
              ? "注册后需由管理员审批，通过后即可使用。"
              : "使用账号密码登录，无需在浏览器粘贴 Key。"
          }}
        </p>
        <form @submit.prevent="submit">
          <label v-if="registering" class="field"
            >姓名 / 显示名称<input
              v-model="displayName"
              required
              maxlength="60"
              placeholder="便于管理员识别你的身份"
              autocomplete="name" /></label
          ><label class="field"
            >用户名<input
              v-model="username"
              required
              minlength="3"
              maxlength="32"
              pattern="[A-Za-z0-9][A-Za-z0-9_.\-]{2,31}"
              placeholder="3–32 位字母、数字、点、下划线或短横线"
              autocomplete="username"
              autocapitalize="none" /></label
          ><label class="field"
            >密码<input
              v-model="password"
              required
              type="password"
              :minlength="registering ? 10 : 1"
              maxlength="128"
              :autocomplete="registering ? 'new-password' : 'current-password'"
              :placeholder="
                registering ? '10–128 个字符' : '输入账号密码'
              " /></label
          ><label v-if="registering" class="field"
            >确认密码<input
              v-model="confirmation"
              required
              type="password"
              minlength="10"
              maxlength="128"
              autocomplete="new-password"
              placeholder="再次输入密码"
          /></label>
          <p v-if="error" class="error-text" role="alert">{{ error }}</p>
          <button class="button primary wide" :disabled="busy">
            <LoaderCircle v-if="busy" class="spin" :size="17" /><UserPlus
              v-else-if="registering"
              :size="17"
            /><LogIn v-else :size="17" />{{
              busy ? "提交中…" : registering ? "注册并申请入网" : "登录工作台"
            }}
          </button>
        </form>
        <p class="hint auth-footnote">
          {{
            registering
              ? "请使用真实可识别的姓名。用户名创建后不可修改。"
              : "忘记密码请联系管理员；已有 API Key 可通过下方入口访问。"
          }}
        </p>
        <button class="text-link legacy-login" @click="keyDialogOpen = true">
          <KeyRound :size="14" />使用已有 API Key
        </button></template
      >
    </div>
  </section>
</template>
