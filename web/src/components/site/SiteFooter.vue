<script setup>
import BrandMark from "../ui/BrandMark.vue";
import { ArrowUpRight, Github } from "lucide-vue-next";
</script>
<template>
  <footer class="site-footer">
    <div class="site-container">
      <div class="site-footer-main">
        <div class="site-footer-brand">
          <RouterLink to="/"><BrandMark /></RouterLink>
          <p>让平台知识触手可及，<br />让团队经验持续生长。</p>
        </div>
        <div class="footer-link-group">
          <strong>工作空间</strong
          ><RouterLink to="/workspace">知识检索</RouterLink
          ><RouterLink to="/rules">开发规范</RouterLink
          ><RouterLink to="/contribute">经验沉淀</RouterLink>
        </div>
        <div class="footer-link-group">
          <strong>开始使用</strong
          ><RouterLink to="/register">注册入网</RouterLink
          ><RouterLink to="/account">个人 Key</RouterLink
          ><RouterLink to="/guide">接入指南</RouterLink>
        </div>
        <div class="footer-link-group">
          <strong>开发资源</strong
          ><a href="/docs" target="_blank" rel="noopener"
            >API 文档 <ArrowUpRight :size="12" /></a
          ><a
            href="https://github.com/aaa123445/v8-workbench"
            target="_blank"
            rel="noopener"
            >GitHub <Github :size="13" /></a
          ><a
            href="/static/licenses/shadcn-vue-landing-page.txt"
            target="_blank"
            rel="noopener"
            >模板许可 <ArrowUpRight :size="12"
          /></a>
        </div>
      </div>
      <div class="site-footer-bottom">
        <span
          >© {{ new Date().getFullYear() }} TeamKB. Built for developers.</span
        ><span><i class="status-dot online" />知识有据，开发有序。</span>
      </div>
    </div>
  </footer>
</template>
