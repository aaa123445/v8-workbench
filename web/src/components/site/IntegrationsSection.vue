<script setup>
import { ref, computed } from "vue";
import {
  Terminal,
  Blocks,
  Workflow,
  ArrowUpRight,
  Copy,
  Check,
} from "lucide-vue-next";
import { notify } from "../../composables/workspace";
const selected = ref(0),
  copied = ref(false);
const integrations = [
  {
    name: "MCP",
    icon: Blocks,
    subtitle: "让 Agent 直接调用知识工具",
    description:
      "在 Codex、Claude Code 等支持 MCP 的客户端启动本地 stdio 代理。查规范、搜文档、读正文，都可以在对话中完成。",
    file: "~/.codex/config.toml",
    code: '[mcp_servers.team-knowledge]\ncommand = "/absolute/path/.venv/bin/wb"\nargs = ["mcp"]\nenv_vars = ["TEAMKB_URL", "TEAMKB_KEY"]',
    section: 5,
  },
  {
    name: "Skill",
    icon: Workflow,
    subtitle: "让知识检索成为工作习惯",
    description:
      "把查规范、读文档、实施、自查和沉淀组成一套可复用流程。配合已经接通的 MCP 或 CLI，让 Agent 知道何时使用知识。",
    file: "在客户端仓库目录执行",
    code: 'mkdir -p "$HOME/.agents/skills"\ncp -R skill/team-knowledge \\\n  "$HOME/.agents/skills/"\n\n# 重开会话，使用 team-knowledge skill',
    section: 6,
  },
  {
    name: "CLI",
    icon: Terminal,
    subtitle: "从终端，到你的自动化脚本",
    description:
      "用命令行完成检索、规范查阅和批量知识提交。结构化 JSON 输出，适合脚本、开发流程和自研 Agent。",
    file: "终端 · 已安装 wb 客户端",
    code: 'export TEAMKB_URL="https://www.ljc.monster"\nexport TEAMKB_KEY="YOUR_PERSONAL_KEY"\n\nwb stats\nwb --json search "组织同步"',
    section: 7,
  },
];
const active = computed(() => integrations[selected.value]);
async function copy() {
  try {
    await navigator.clipboard.writeText(active.value.code);
    copied.value = true;
    setTimeout(() => (copied.value = false), 1800);
  } catch {
    notify("复制失败，请手动选择配置内容。", "error");
  }
}
function choose(index) {
  selected.value = index;
  copied.value = false;
}
</script>
<template>
  <section
    id="integrations"
    class="site-section site-container integration-section"
  >
    <div class="integration-intro">
      <span class="site-kicker">ONE KNOWLEDGE BASE. YOUR TOOLS.</span>
      <h2>你熟悉的工具，<br />同一个知识来源。</h2>
      <p>
        不必离开你的开发节奏。选择合适的接入方式，把团队知识带到需要它的地方。
      </p>
      <div class="integration-options" aria-label="选择接入方式">
        <button
          v-for="(item, index) in integrations"
          :key="item.name"
          :class="{ active: selected === index }"
          :aria-pressed="selected === index"
          @click="choose(index)"
        >
          <component :is="item.icon" :size="21" /><span
            ><strong>{{ item.name }}</strong
            ><small>{{ item.subtitle }}</small></span
          ><ArrowUpRight :size="17" />
        </button>
      </div>
    </div>
    <div class="integration-detail">
      <div class="code-window">
        <div class="code-window-header">
          <span class="window-dots"><i /><i /><i /></span
          ><span>{{ active.file }}</span
          ><button
            class="icon-button"
            :aria-label="`复制 ${active.name} 配置`"
            @click="copy"
          >
            <Check v-if="copied" :size="16" /><Copy v-else :size="16" />
          </button>
        </div>
        <pre><code>{{ active.code }}</code></pre>
        <div class="code-window-foot">
          <span class="status-dot online" />{{
            active.name === "MCP"
              ? "本地 stdio 代理 → 工作台 HTTPS API"
              : active.name === "Skill"
                ? "流程说明 → MCP 或 CLI → 知识工作台"
                : "你的终端 → 工作台 HTTPS API"
          }}
        </div>
      </div>
      <p>{{ active.description }}</p>
      <RouterLink
        :to="{ path: '/guide', query: { section: active.section } }"
        class="text-link"
        >查看 {{ active.name }} 完整安装指南<ArrowUpRight :size="15"
      /></RouterLink>
    </div>
  </section>
</template>
