<script setup>
import { ref } from "vue";
import {
  CheckCheck,
  TriangleAlert,
  ArrowUpRight,
  BookOpen,
} from "lucide-vue-next";
import { post } from "../services/api";
import { useResource } from "../composables/useResource";
import AsyncState from "../components/AsyncState.vue";
const picked = ref("spi"),
  checked = ref([]);
const profiles = [
  ["spi", "后端 SPI 扩展"],
  ["udc", "UDC 应用 / 组件"],
  ["bpm", "BPM 流程扩展"],
  ["frontend", "前端扩展"],
  ["integration", "集成平台"],
  ["data", "数据库 / 迁移"],
  ["docs", "交付文档"],
  ["general", "通用客开"],
];
const { data, loading, error, reload } = useResource(() => {
  checked.value = [];
  return post("/rules", { task: picked.value, include_docs: false });
}, [picked]);
</script>
<template>
  <section>
    <div class="page-heading">
      <div>
        <div class="eyebrow section-eyebrow">BUILD WITH CONFIDENCE</div>
        <h1>开发规范</h1>
        <p>从任务出发，把分散的规范变成可执行的开发清单。</p>
      </div>
      <span class="page-icon"><BookOpen :size="30" /></span>
    </div>
    <div class="tabs panel">
      <button
        v-for="[key, label] in profiles"
        :key="key"
        :class="['chip', { active: picked === key }]"
        @click="picked = key"
      >
        {{ label }}
      </button>
    </div>
    <AsyncState :loading="loading" :error="error" @retry="reload"
      ><template v-if="data"
        ><div class="rules-banner">
          <div>
            <span class="eyebrow">当前任务画像</span>
            <h2>{{ data.name }}</h2>
            <p>动手前确认规范，提交前完成自查。</p>
          </div>
          <div>
            <strong>{{ checked.length }} / {{ data.checklist.length }}</strong
            ><span>自查完成</span>
          </div>
        </div>
        <div class="two-columns">
          <div class="panel">
            <div class="section-heading">
              <h2><CheckCheck :size="20" />提交前自查</h2>
              <span class="badge green">{{ data.checklist.length }} 项</span>
            </div>
            <label
              v-for="(item, i) in data.checklist"
              :key="item"
              class="check-item"
              :class="{ checked: checked.includes(i) }"
              ><input v-model="checked" type="checkbox" :value="i" /><span>{{
                item
              }}</span></label
            >
          </div>
          <div>
            <div class="panel pitfalls">
              <h2><TriangleAlert :size="19" />常见问题与提醒</h2>
              <ul>
                <li v-for="item in data.pitfalls" :key="item">{{ item }}</li>
              </ul>
              <p v-if="!data.pitfalls.length" class="muted">
                当前任务暂无额外提醒。
              </p>
            </div>
            <div class="panel">
              <h2><BookOpen :size="19" />必读文档</h2>
              <RouterLink
                v-for="doc in data.documents_index"
                :key="doc.id"
                :to="{ name: 'document', params: { id: doc.id } }"
                class="document-row"
                ><span>{{ doc.title }}</span
                ><ArrowUpRight :size="16"
              /></RouterLink>
              <p v-if="!data.documents_index?.length" class="muted">
                当前知识库暂未收录对应文档。
              </p>
            </div>
          </div>
        </div></template
      ></AsyncState
    >
  </section>
</template>
