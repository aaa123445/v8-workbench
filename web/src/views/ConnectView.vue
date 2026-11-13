<script setup>
import {
  computed,
  ref,
  onMounted,
  onBeforeUnmount,
  watch,
  nextTick,
} from "vue";
import { useRoute } from "vue-router";
import {
  PlugZap,
  Copy,
  Check,
  ArrowRight,
  KeyRound,
  LoaderCircle,
  RefreshCw,
} from "lucide-vue-next";
import { currentUser } from "../composables/session";
import { apiKey, notify } from "../composables/workspace";
import { takeConnectionKey } from "../composables/connection";
import { post } from "../services/api";
import { connectionPrompt, modes } from "../services/connectionPrompt";
import "../styles/connect.css";
const route = useRoute();
const mode = ref(
  modes.some((m) => m.id === route.query.mode)
    ? route.query.mode
    : "recommended",
);
const key = ref(takeConnectionKey()),
  includeKey = ref(!!key.value),
  autoSubmit = ref(false);
const manifest = ref(null),
  loading = ref(false),
  error = ref(""),
  creating = ref(false),
  copied = ref(false);
const keyName = ref("本地 Agent 接入"),
  role = ref("reader");
const canCreate = computed(() => currentUser.value?.status === "approved");
const canWrite = computed(() =>
  ["writer", "admin"].includes(currentUser.value?.role),
);
const origin = window.location.origin;
const prompt = computed(() =>
  manifest.value
    ? connectionPrompt({
        origin,
        mode: mode.value,
        manifest: manifest.value,
        key: includeKey.value ? key.value.trim() : "",
        autoSubmit: autoSubmit.value,
      })
    : "",
);
const preview = computed(() =>
  includeKey.value && key.value.trim()
    ? prompt.value.replace(
        JSON.stringify(key.value.trim()),
        '"[个人 Key 已隐藏，复制时包含]"',
      )
    : prompt.value,
);
const controller = new AbortController();
let copyTimer;
async function loadManifest() {
  loading.value = true;
  error.value = "";
  try {
    const response = await fetch("/static/downloads/manifest.json", {
      cache: "no-store",
      signal: controller.signal,
    });
    if (!response.ok) throw new Error("无法读取客户端校验清单，请稍后重试。");
    const data = await response.json();
    // Validate all modes before enabling copy.
    connectionPrompt({ origin, mode: "recommended", manifest: data });
    manifest.value = data;
  } catch (e) {
    if (e.name !== "AbortError") error.value = e.message;
  } finally {
    loading.value = false;
  }
}
async function createKey() {
  creating.value = true;
  try {
    const result = await post(
      "/account/keys",
      { name: keyName.value.trim(), role: role.value },
      { key: "" },
    );
    key.value = result.key;
    includeKey.value = true;
    notify("专用 Key 已创建，复制提示词即可交给本地 Agent");
  } catch (e) {
    notify(e.message, "error");
  } finally {
    creating.value = false;
  }
}
async function copyPrompt() {
  try {
    await navigator.clipboard.writeText(prompt.value);
    copied.value = true;
    clearTimeout(copyTimer);
    copyTimer = setTimeout(() => (copied.value = false), 3000);
    notify(
      includeKey.value && key.value.trim()
        ? "已复制含个人 Key 的安装提示词，请交给你信任的本地 Agent"
        : "安装提示词已复制，本地 Agent 会引导填写 Key",
    );
  } catch {
    notify("剪贴板不可用，请使用下方“选中提示词”手动复制", "error");
  }
}
const manualText = ref(null),
  manualCopy = ref(false);
async function selectPrompt() {
  manualCopy.value = true;
  await nextTick();
  manualText.value?.focus();
  manualText.value?.select();
}
watch([mode, key, includeKey, autoSubmit], () => {
  copied.value = false;
  manualCopy.value = false;
});
onMounted(loadManifest);
onBeforeUnmount(() => {
  controller.abort();
  clearTimeout(copyTimer);
  key.value = "";
});
</script>
<template>
  <section class="connect-page">
    <div class="page-heading">
      <div>
        <div class="eyebrow section-eyebrow">CONNECT YOUR LOCAL AGENT</div>
        <h1>一键接入</h1>
        <p>复制安装提示词，交给本地 Agent，完成安装、配置与连接验证。</p>
      </div>
      <RouterLink to="/guide" class="button"
        >完整使用说明 <ArrowRight :size="15"
      /></RouterLink>
    </div>
    <div class="connect-banner">
      <span class="connect-logo"><PlugZap :size="30" /></span>
      <div>
        <h2>把团队知识带到你的开发现场</h2>
        <p>
          1 选择接入方式 <ArrowRight :size="13" /> 2 配置个人 Key
          <ArrowRight :size="13" /> 3 复制给 Agent 安装
        </p>
      </div>
    </div>
    <div class="connect-layout">
      <div class="connect-settings">
        <section class="panel connect-panel">
          <h2><span class="connect-number">1</span>选择接入方式</h2>
          <div class="connect-modes">
            <button
              v-for="item in modes"
              :key="item.id"
              :class="['connect-mode', { active: mode === item.id }]"
              :aria-pressed="mode === item.id"
              @click="mode = item.id"
            >
              <span
                ><strong>{{ item.title }}</strong
                ><Check v-if="mode === item.id" :size="17" /></span
              ><small>{{ item.description }}</small>
            </button>
          </div>
          <div class="connect-server">
            <span>当前团队服务</span><code>{{ origin }}</code>
          </div>
        </section>
        <section class="panel connect-panel">
          <h2><span class="connect-number">2</span>个人访问凭据</h2>
          <p class="connect-help">
            可以先复制提示词，在本机填写 Key；也可在这里配置，随提示词一起交给
            Agent。
          </p>
          <label class="field"
            >已有个人 Key<input
              v-model="key"
              type="password"
              autocomplete="off"
              spellcheck="false"
              placeholder="粘贴个人 Key（可留空）"
          /></label>
          <button
            v-if="apiKey && !currentUser"
            class="text-link"
            @click="
              key = apiKey;
              includeKey = true;
            "
          >
            使用当前访问 Key
          </button>
          <label class="connect-check"
            ><input
              v-model="includeKey"
              type="checkbox"
              :disabled="!key.trim()"
            /><span
              >复制时包含个人 Key<small
                >预览中隐藏；仅交给你信任的本地 Agent。页面不保存这里填写的
                Key。</small
              ></span
            ></label
          >
          <details v-if="canCreate" class="connect-create">
            <summary><KeyRound :size="15" />创建接入专用 Key</summary>
            <form @submit.prevent="createKey">
              <label class="field"
                >名称<input v-model="keyName" required maxlength="80" /></label
              ><label class="field"
                >权限<select v-model="role">
                  <option value="reader">reader · 检索与阅读</option>
                  <option v-if="canWrite" value="writer">
                    writer · 可提交经验
                  </option>
                </select></label
              ><button class="button" :disabled="creating || !keyName.trim()">
                <LoaderCircle
                  v-if="creating"
                  :size="15"
                  class="spin"
                />创建并用于提示词
              </button>
              <p class="connect-help">
                创建后勾选“包含个人 Key”。请在离开前复制保存，完整 Key
                仅显示本次；可在个人中心吊销。
              </p>
              <input
                v-if="key"
                :value="key"
                type="password"
                readonly
                aria-label="本次接入 Key"
              />
            </form>
          </details>
          <RouterLink v-else to="/account" class="text-link"
            >{{
              currentUser
                ? "账号审批通过后可创建个人 Key"
                : "前往个人中心创建 Key"
            }}
            <ArrowRight :size="14"
          /></RouterLink>
        </section>
        <section class="panel connect-panel">
          <h2>经验沉淀</h2>
          <label class="connect-check"
            ><input v-model="autoSubmit" type="checkbox" /><span
              >在当前开发项目启用经验候选提交<small
                >需要 writer
                权限。仅提交经过验证、脱敏的方案，默认由管理员审核后共享。</small
              ></span
            ></label
          >
        </section>
      </div>
      <section class="panel connect-output">
        <div class="connect-output-heading">
          <div>
            <span class="eyebrow">READY FOR YOUR AGENT</span>
            <h2><span class="connect-number">3</span>安装提示词</h2>
          </div>
          <span class="badge">{{
            modes.find((m) => m.id === mode)?.title
          }}</span>
        </div>
        <p class="connect-help">
          直接发给正在使用的本地
          Agent。它会识别系统与客户端、保留已有配置，并反馈真实连接状态。
        </p>
        <div v-if="loading" class="connect-loading">
          <LoaderCircle :size="20" class="spin" />正在读取客户端校验信息…
        </div>
        <div v-else-if="error" role="alert" class="connect-error">
          <p>{{ error }}</p>
          <button class="button" @click="loadManifest">
            <RefreshCw :size="14" />重新加载
          </button>
        </div>
        <template v-else>
          <pre class="connect-preview" aria-label="安装提示词预览">{{
            preview
          }}</pre>
          <div class="connect-copy-actions">
            <button
              class="button primary"
              :disabled="!prompt"
              @click="copyPrompt"
            >
              <Check v-if="copied" :size="17" /><Copy v-else :size="17" />{{
                copied ? "已复制" : "复制安装提示词"
              }}</button
            ><button class="text-link" @click="selectPrompt">选中提示词</button>
          </div>
          <div v-if="manualCopy" class="connect-manual">
            <p class="connect-help">
              {{
                includeKey && key.trim()
                  ? "下方包含完整个人 Key，请仅复制给本地 Agent。"
                  : "点击文本框即可全选，再手动复制。"
              }}
            </p>
            <textarea
              ref="manualText"
              :value="prompt"
              readonly
              aria-label="手动复制安装提示词"
              @focus="$event.target.select()"
              @click="$event.target.select()"
            />
          </div>
          <p class="connect-help connect-bottom-note">
            {{
              includeKey && key.trim()
                ? "复制内容包含个人 Key。"
                : "未包含 Key，本地 Agent 会引导你在本机配置。"
            }}安装完成后，以 Agent 返回的鉴权和工具调用结果确认接入。
          </p></template
        >
      </section>
    </div>
  </section>
</template>
