<script setup>
import { ask } from "../composables/confirmation";
import { ref } from "vue";
import {
  KeyRound,
  Plus,
  RefreshCw,
  Trash2,
  Copy,
  Database,
  ShieldCheck,
  LoaderCircle,
} from "lucide-vue-next";
import { api, post } from "../services/api";
import { notify, refreshStats } from "../composables/workspace";
import { useResource } from "../composables/useResource";
import AccountApprovals from "../components/AccountApprovals.vue";
import AsyncState from "../components/AsyncState.vue";
import AgentSettings from "../components/AgentSettings.vue";
const { data, loading, error, reload } = useResource(async () => {
  const [keys, usage] = await Promise.all([
    api("/admin/keys"),
    api("/admin/usage"),
  ]);
  return { ...keys, ...usage };
});
const name = ref(""),
  role = ref("writer"),
  newKey = ref(""),
  createBusy = ref(false),
  syncBusy = ref(false),
  rebuildBusy = ref(false),
  revokedBusy = ref(""),
  syncResult = ref(null);
async function create() {
  if (!name.value.trim()) return;
  createBusy.value = true;
  try {
    const result = await post("/admin/keys", {
      name: name.value.trim(),
      role: role.value,
    });
    newKey.value = result.key;
    name.value = "";
    notify("新的 API Key 已创建，请立即保存");
    await reload();
  } catch (e) {
    notify(e.message, "error");
  } finally {
    createBusy.value = false;
  }
}
async function policy(key) {
  if (
    !key.auto_publish &&
    !(await ask(
      "允许此 Key 为材料完整、无相似知识的 Agent 方案自动发布？所有操作会留痕。",
    ))
  )
    return;
  try {
    await api("/admin/keys/" + encodeURIComponent(key.key_prefix) + "/policy", {
      method: "PUT",
      body: { auto_publish: !key.auto_publish },
    });
    notify("自动发布策略已更新");
    await reload();
  } catch (e) {
    notify(e.message, "error");
  }
}
async function revoke(key) {
  if (
    !(await ask(
      `确认吊销「${key.name}」(${key.key_prefix})？使用此 Key 的客户端将无法继续访问。`,
    ))
  )
    return;
  revokedBusy.value = key.key_prefix;
  try {
    await api("/admin/keys/" + encodeURIComponent(key.key_prefix), {
      method: "DELETE",
    });
    notify("Key 已吊销");
    await reload();
  } catch (e) {
    notify(e.message, "error");
  } finally {
    revokedBusy.value = "";
  }
}
async function sync() {
  syncBusy.value = true;
  syncResult.value = null;
  try {
    syncResult.value = await post("/admin/sync/yuque");
    notify(
      `同步完成：新增 ${syncResult.value.created}，更新 ${syncResult.value.updated}，失败 ${syncResult.value.failed}`,
    );
    refreshStats().catch(() => {});
  } catch (e) {
    notify(
      e.message + " 长时间同步可能仍在服务端执行，请稍后刷新查看。",
      "error",
    );
  } finally {
    syncBusy.value = false;
  }
}
async function rebuild() {
  rebuildBusy.value = true;
  try {
    const result = await post("/admin/rebuild");
    notify(`索引已重建，共 ${result.indexed} 篇文档`);
    refreshStats().catch(() => {});
  } catch (e) {
    notify(e.message, "error");
  } finally {
    rebuildBusy.value = false;
  }
}
async function copy() {
  try {
    await navigator.clipboard.writeText(newKey.value);
    notify("已复制新 Key");
  } catch {
    notify("复制失败，请手动选择并保存 Key", "error");
  }
}
</script>
<template>
  <section>
    <div class="page-heading">
      <div>
        <div class="eyebrow section-eyebrow">WORKSPACE SETTINGS</div>
        <h1>工作台管理</h1>
        <p>管理访问权限、同步知识库，让协作有序进行。</p>
      </div>
      <span class="badge green"><ShieldCheck :size="14" />管理员空间</span>
    </div>
    <AccountApprovals />
    <AgentSettings />
    <AsyncState :loading="loading" :error="error" @retry="reload"
      ><template v-if="data"
        ><div class="panel">
          <div class="section-heading">
            <h2><KeyRound :size="19" />API Key 管理</h2>
            <button
              class="icon-button"
              aria-label="刷新 Key 列表"
              @click="reload"
            >
              <RefreshCw :size="16" />
            </button>
          </div>
          <p class="muted">按使用场景分配访问凭据，遵循最小权限原则。</p>
          <div v-if="newKey" class="new-key-box" role="status">
            <strong>新 Key 仅显示这一次，请立即复制保存</strong>
            <div>
              <code>{{ newKey }}</code><button
                class="button small"
                @click="copy"
              >
                <Copy :size="14" />复制
              </button>
            </div>
            <button class="text-link" @click="newKey = ''">
              我已保存，关闭显示
            </button>
          </div>
          <div class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>名称 / 前缀</th>
                  <th>角色</th>
                  <th>今日用量</th>
                  <th>状态</th>
                  <th class="align-right">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="key in data.keys" :key="key.key_prefix">
                  <td>
                    <strong>{{ key.name }}</strong><span class="table-secondary"
                      >归属：{{ key.owner_username || "旧版 / 系统 Key" }}</span
                    ><code class="table-secondary">{{ key.key_prefix }}</code>
                  </td>
                  <td>
                    <span class="badge">{{ key.role }}</span>
                  </td>
                  <td>
                    {{ key.used_today }}
                    <span class="muted">/ {{ key.daily_limit }}</span>
                  </td>
                  <td>
                    <span :class="['badge', { green: key.enabled }]">{{
                      key.enabled ? "启用中" : "已吊销"
                    }}</span>
                  </td>
                  <td class="align-right">
                    <button
                      v-if="key.enabled && key.role !== 'reader'"
                      class="button small"
                      @click="policy(key)"
                    >
                      {{ key.auto_publish ? "关闭自动发布" : "授权自动发布" }}
                    </button>
                    <button
                      v-if="key.enabled"
                      class="button small danger"
                      :disabled="!!revokedBusy"
                      @click="revoke(key)"
                    >
                      <Trash2 :size="13" />吊销</button
                    ><span v-else class="muted">—</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <form class="create-key-form" @submit.prevent="create">
            <label class="field"
              >Key 名称<input
                v-model="name"
                required
                placeholder="例如：开发团队 Agent" /></label
            ><label class="field"
              >权限角色<select v-model="role">
                <option value="reader">reader · 只读</option>
                <option value="writer">writer · 读写</option>
                <option value="admin">admin · 管理员</option>
              </select></label
            ><button
              class="button primary"
              :disabled="createBusy || !name.trim()"
            >
              <LoaderCircle v-if="createBusy" class="spin" :size="15" /><Plus
                v-else
                :size="16"
              />创建 Key
            </button>
          </form>
        </div>
        <div class="quick-grid admin-tools">
          <div class="panel">
            <span class="feature-icon"><RefreshCw :size="22" /></span>
            <h2>语雀知识同步</h2>
            <p class="muted">
              增量同步平台文档，更新后自动重建索引。全量同步可能需要数分钟，请耐心等待。
            </p>
            <button
              class="button"
              :disabled="syncBusy || rebuildBusy"
              @click="sync"
            >
              <RefreshCw :size="15" :class="{ spin: syncBusy }" />{{
                syncBusy ? "正在同步，请勿重复提交…" : "同步语雀知识库"
              }}
            </button>
            <div v-if="syncResult" class="sync-report">
              <p>
                新增 {{ syncResult.created }} · 更新 {{ syncResult.updated }} ·
                失败 {{ syncResult.failed }}
              </p>
              <details v-if="syncResult.errors?.length">
                <summary>查看失败详情</summary>
                <p v-for="item in syncResult.errors" :key="item.title">
                  {{ item.title }}：{{ item.error }}
                </p>
              </details>
            </div>
          </div>
          <div class="panel">
            <span class="feature-icon violet"><Database :size="22" /></span>
            <h2>检索索引</h2>
            <p class="muted">
              文档变更后通常会自动更新。需要刷新检索数据时，可手动重建知识库索引。
            </p>
            <button
              class="button"
              :disabled="rebuildBusy || syncBusy"
              @click="rebuild"
            >
              <RefreshCw :size="15" :class="{ spin: rebuildBusy }" />{{
                rebuildBusy ? "重建中…" : "重建检索索引"
              }}
            </button>
          </div>
        </div>
        <div class="panel">
          <div class="section-heading">
            <h2>近期调用记录</h2>
            <span class="badge">按日汇总</span>
          </div>
          <div v-if="data.usage?.length" class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>日期</th>
                  <th>Key 前缀</th>
                  <th>调用次数</th>
                  <th>失败次数</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="item in data.usage"
                  :key="item.key_prefix + item.day"
                >
                  <td>{{ item.day }}</td>
                  <td>
                    <code>{{ item.key_prefix }}</code>
                  </td>
                  <td>{{ item.calls }}</td>
                  <td>{{ item.errors }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-else class="muted">暂无调用记录。</p>
        </div></template
      ></AsyncState
    >
  </section>
</template>
