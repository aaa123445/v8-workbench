<script setup>
// Question/answer model and accordion layout adapted from template FAQ.vue (MIT).
import { Plus } from "lucide-vue-next";
const questions = [
  {
    question: "注册之后，可以直接使用吗？",
    answer:
      "注册后账号处于待审批状态。管理员核实身份并分配角色后，即可使用知识库。你可以登录个人中心查看审批状态。",
  },
  {
    question: "浏览器登录和 API Key 有什么区别？",
    answer:
      "账号密码用于登录网页；个人 Key 用于 MCP 和 CLI 等客户端。网页获批登录后无需粘贴 Key。每个账号可在个人中心创建和吊销自己的 Key。",
  },
  {
    question: "MCP、Skill、CLI 应该选哪一种？",
    answer:
      "MCP 让 Agent 调用知识工具；Skill 约定如何检索、遵循规范与沉淀经验；CLI 面向终端和脚本。MCP 与 Skill 可以组合使用，CLI 也可以独立使用。",
  },
  {
    question: "网站地址可以直接作为远程 MCP 地址吗？",
    answer:
      "当前项目提供本地 stdio MCP 代理。先在开发电脑安装客户端，再通过 wb mcp 启动，由它调用工作台 HTTPS API。完整配置见使用说明。",
  },
  {
    question: "普通账号能管理别人的 Key 吗？",
    answer:
      "普通账号只能查看、创建和吊销自己的 Key，权限不能超过账号角色。全局 Key 管理、账号审批和知识同步需要管理员权限。",
  },
];
</script>
<template>
  <section id="faq" class="site-section site-container faq-section">
    <div class="site-section-heading">
      <span class="site-kicker">A FEW THINGS TO KNOW</span>
      <h2>开始之前，你可能想知道。</h2>
      <p>
        更多安装步骤与排查方法，都在<RouterLink to="/guide">使用说明</RouterLink
        >中。
      </p>
    </div>
    <div class="faq-list">
      <details
        v-for="item in questions"
        :key="item.question"
        name="landing-faq"
      >
        <summary>{{ item.question }}<Plus :size="18" /></summary>
        <p>{{ item.answer }}</p>
      </details>
    </div>
  </section>
</template>
