<script setup>
// Step structure adapted from HowItWorks.vue in the MIT Shadcn/Vue Landing Page template.
import { UserPlus, ShieldCheck, PlugZap, ArrowUpRight } from "lucide-vue-next";
const steps = [
  {
    icon: UserPlus,
    number: "01",
    title: "创建你的账号",
    description: "填写用户名与可识别的姓名，提交入网申请。",
    label: "注册入网",
    to: "/register",
  },
  {
    icon: ShieldCheck,
    number: "02",
    title: "审批后，进入工作空间",
    description: "由管理员核实身份并分配角色，获批后即可使用知识库。",
    label: "查看我的状态",
    to: "/account",
  },
  {
    icon: PlugZap,
    number: "03",
    title: "连接你熟悉的开发工具",
    description:
      "创建个人 Key，配置 MCP、Skill 或 CLI，让知识进入你的日常开发。",
    label: "阅读接入指南",
    to: "/guide",
  },
];
</script>
<template>
  <section id="workflow" class="workflow-band">
    <div class="site-container site-section">
      <div class="site-section-heading">
        <span class="site-kicker">A SIMPLE START</span>
        <h2>三步，连接你的知识工作空间。</h2>
        <p>网页直接使用，开发工具按需连接。第一次接入，也有清晰的路径。</p>
      </div>
      <div class="workflow-grid">
        <article v-for="step in steps" :key="step.number" class="workflow-step">
          <div class="workflow-step-top">
            <span><component :is="step.icon" :size="22" /></span
            ><b>{{ step.number }}</b>
          </div>
          <h3>{{ step.title }}</h3>
          <p>{{ step.description }}</p>
          <RouterLink :to="step.to"
            >{{ step.label }}<ArrowUpRight :size="15"
          /></RouterLink>
        </article>
      </div>
    </div>
  </section>
</template>
