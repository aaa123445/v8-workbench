<script setup>
// Data-driven feature grid adapted from the MIT Shadcn/Vue Landing Page template.
import {
  Search,
  ListChecks,
  NotebookPen,
  KeyRound,
  Terminal,
  RefreshCw,
  ArrowUpRight,
} from "lucide-vue-next";
import SurfaceCard from "../ui/SurfaceCard.vue";
const features = [
  {
    icon: Search,
    title: "知识检索，有出处可追溯",
    description:
      "从标题、知识领域和正文中找到相关文档，打开完整内容，确认适用版本。",
    label: "从问题到依据",
    to: "/workspace",
  },
  {
    icon: ListChecks,
    title: "开发规范，成为执行清单",
    description:
      "按知识分类配置团队规范与检查清单，动手前明确边界，提交前逐项自查。",
    label: "从规范到行动",
    to: "/rules",
  },
  {
    icon: NotebookPen,
    title: "一次解决，成为团队经验",
    description:
      "Agent 自动整理经过验证的解法，经审核发布并保留版本，让团队持续复用。",
    label: "从个人到团队",
    to: "/contribute",
  },
  {
    icon: Terminal,
    title: "接入 Agent，融入你的流程",
    description:
      "用 MCP 调用工具，以 Skill 约定流程，通过 CLI 完成脚本化检索和经验提交。",
    label: "从知识到工具",
    to: { path: "/guide", query: { section: 2 } },
  },
  {
    icon: KeyRound,
    title: "个人凭据，访问边界清晰",
    description:
      "注册后由管理员审批。每个账号管理自己的 Key，按使用场景分配只读或读写权限。",
    label: "从协作到治理",
    to: "/account",
  },
  {
    icon: RefreshCw,
    title: "同步与沉淀，持续生长",
    description:
      "语雀文档与团队经验汇入同一知识库。增量同步、检索索引和来源信息统一管理。",
    label: "从积累到复用",
    to: "/overview",
  },
];
</script>
<template>
  <section id="features" class="site-section site-container">
    <div class="site-section-heading">
      <span class="site-kicker">BUILT AROUND YOUR WORKFLOW</span>
      <h2>知识，不该散落在各处。</h2>
      <p>把检索、规范和经验连接起来，让每一步开发都能接住已有的积累。</p>
    </div>
    <div class="site-feature-grid">
      <SurfaceCard
        v-for="feature in features"
        :key="feature.title"
        class="site-feature-card"
        ><span class="site-feature-icon"
          ><component :is="feature.icon" :size="23" /></span
        ><span class="feature-category">{{ feature.label }}</span>
        <h3>{{ feature.title }}</h3>
        <p>{{ feature.description }}</p>
        <RouterLink :to="feature.to"
          >了解更多 <ArrowUpRight :size="15" /></RouterLink
      ></SurfaceCard>
    </div>
  </section>
</template>
