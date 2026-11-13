<script setup>
// Adapted from leoMirandaa/shadcn-vue-landing-page/src/components/Hero.vue (MIT).
import {
  ArrowRight,
  ArrowUpRight,
  Sparkles,
  BookOpen,
  Check,
} from "lucide-vue-next";
import { currentUser, hasAccess } from "../../composables/session";
import { serviceHealth } from "../../composables/workspace";
import WorkbenchPreview from "./WorkbenchPreview.vue";
</script>
<template>
  <section class="site-hero">
    <div class="hero-grid-bg" aria-hidden="true" />
    <div class="site-container hero-container">
      <div class="release-pill">
        <span><Sparkles :size="13" /> 为团队与 Agent 构建</span><i /><span
          >你的团队知识，现在互相连接<ArrowUpRight :size="13"
        /></span>
      </div>
      <h1>
        让知识流动，<br />让每一次开发<span class="gradient-text"
          >都有依据。</span
        >
      </h1>
      <p class="hero-description">
        连接分类知识、团队规范与验证过的解决方案。<br
          class="desktop-break"
        />让你和 AI Agent，共用一个可靠的知识工作空间。
      </p>
      <div class="hero-actions">
        <RouterLink
          :to="
            hasAccess ? '/workspace' : currentUser ? '/account' : '/register'
          "
          class="button primary large"
          >{{
            hasAccess
              ? "打开我的工作台"
              : currentUser
                ? "查看入网状态"
                : "开始使用工作台"
          }}<ArrowRight :size="18" /></RouterLink
        ><RouterLink to="/guide" class="button large"
          >阅读接入指南<ArrowUpRight :size="17"
        /></RouterLink>
      </div>
      <div class="hero-facts">
        <span><Check :size="14" />注册审批后使用</span
        ><span><Check :size="14" />个人 API Key</span
        ><span><Check :size="14" />MCP · Skill · CLI</span>
      </div>
      <WorkbenchPreview />
      <div class="hero-bottom-stats">
        <div>
          <strong
            >{{ serviceHealth?.documents?.toLocaleString() ?? "—"
            }}<small>篇</small></strong
          ><span>知识文档 · 实时连接工作台</span>
        </div>
        <div>
          <strong>8<small>类</small></strong
          ><span>分类管理 · 审核发布 · 版本追溯</span>
        </div>
        <div>
          <strong>3<small>种</small></strong
          ><span>接入方式 · 融入你的工具链</span>
        </div>
      </div>
    </div>
  </section>
</template>
