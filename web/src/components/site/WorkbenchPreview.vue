<script setup>
import { ref, computed } from "vue";
import {
  Search,
  ArrowUpRight,
  BookOpen,
  FileText,
  ShieldCheck,
  Terminal,
  Check,
  ChevronRight,
  Command,
  Layers,
} from "lucide-vue-next";
const selected = ref(0);
const topics = [
  {
    label: "组织同步",
    path: "集成平台 / 组织同步",
    title: "先找到依据，再开始实现",
    query: "组织同步 中间表",
    docs: ["组织同步与中间表", "组织同步 SPI 扩展", "集成平台开发规范"],
  },
  {
    label: "SPI 扩展",
    path: "扩展能力 / SPI",
    title: "理解扩展边界，按规范落地",
    query: "SPI 扩展",
    docs: ["后端 SPI 扩展说明", "扩展点接口与实现", "后端开发规范"],
  },
  {
    label: "UDC 页面",
    path: "UDC 平台 / 页面开发",
    title: "把组件规范带进开发流程",
    query: "UDC 自定义页面",
    docs: ["UDC 自定义页面", "平台上下文与组件", "前端开发规范"],
  },
];
const topic = computed(() => topics[selected.value]);
</script>
<template>
  <div class="product-preview" aria-label="工作台功能示意">
    <div class="preview-topbar">
      <span class="window-dots"><i /><i /><i /></span
      ><span><span class="status-dot online" /> TeamKB / 工作流示意</span
      ><span class="preview-secure"
        ><ShieldCheck :size="13" />团队专属空间</span
      >
    </div>
    <div class="preview-body">
      <div class="preview-sidebar">
        <div class="preview-space">
          <span class="preview-space-icon"><Command :size="18" /></span
          ><span>团队知识库 <small>TEAM WORKSPACE</small></span>
        </div>
        <div class="preview-nav-item active"><Search :size="15" />知识检索</div>
        <div class="preview-nav-item"><BookOpen :size="15" />团队规范</div>
        <div class="preview-nav-item"><Layers :size="15" />经验沉淀</div>
        <div class="preview-side-bottom">
          <span class="status-dot online" />知识，即刻连接
        </div>
      </div>
      <div class="preview-workspace">
        <div class="preview-breadcrumb">
          {{ topic.path }}<ChevronRight :size="12" /><span>开发知识</span>
        </div>
        <div class="preview-headline">
          <h2>{{ topic.title }}</h2>
          <span class="badge">WORKFLOW PREVIEW</span>
        </div>
        <RouterLink
          :to="{ name: 'search', query: { q: topic.query } }"
          class="preview-search"
          ><Search :size="18" /><span>{{ topic.query }}</span
          ><span class="preview-search-action"
            >去检索<ArrowUpRight :size="14" /></span
        ></RouterLink>
        <div class="preview-topic-switch">
          <span>探索知识域</span
          ><button
            v-for="(item, index) in topics"
            :key="item.label"
            :class="{ active: selected === index }"
            :aria-pressed="selected === index"
            @click="selected = index"
          >
            {{ item.label }}
          </button>
        </div>
        <div class="preview-flow">
          <div class="preview-document-list">
            <span class="preview-section-label">从文档找到依据</span
            ><RouterLink
              v-for="(title, index) in topic.docs"
              :key="title"
              :to="{ name: 'search', query: { q: title } }"
              class="preview-doc"
              ><span class="preview-file-icon"><FileText :size="17" /></span>
              <div>
                <strong>{{ title }}</strong><small>{{
                  [
                    "定位适用场景与平台版本",
                    "核对接口签名与扩展点",
                    "整理规范与提交前自查",
                  ][index]
                }}</small>
              </div>
              <ArrowUpRight :size="14"
            /></RouterLink>
          </div>
          <div class="preview-agent">
            <div class="preview-agent-heading">
              <span><Terminal :size="15" /> Agent 工作流</span><i />
            </div>
            <div class="preview-agent-step">
              <Check :size="13" /><span
                >获取开发规范 <code>kb_rules</code></span
              >
            </div>
            <div class="preview-agent-step">
              <Check :size="13" /><span
                >检索并阅读文档 <code>kb_search → kb_read</code></span
              >
            </div>
            <div class="preview-agent-step">
              <span class="step-current" /><span
                >基于文档实施<span class="preview-agent-note"
                  >版本、出处、边界，都有迹可循。</span
                ></span
              >
            </div>
            <div class="preview-agent-foot">
              <span class="agent-spark">✦</span> 把依据带进每一步开发
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
