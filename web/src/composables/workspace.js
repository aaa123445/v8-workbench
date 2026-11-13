import { ref } from "vue";
import { api } from "../services/api";
export const apiKey = ref(localStorage.getItem("v8wb_key") || "");
export const authVersion = ref(0);
export const stats = ref(null);
export const serviceHealth = ref(null);
export const notice = ref(null);
export const keyDialogOpen = ref(false);
let noticeTimer;
export function notify(message, kind = "success") {
  clearTimeout(noticeTimer);
  notice.value = { message, kind };
  noticeTimer = setTimeout(() => {
    notice.value = null;
  }, 6000);
}
export async function refreshStats() {
  stats.value = await api("/stats");
  return stats.value;
}
export function saveKey(key) {
  apiKey.value = key;
  if (key) localStorage.setItem("v8wb_key", key);
  else localStorage.removeItem("v8wb_key");
  stats.value = null;
  authVersion.value++;
}
export const sourceLabel = (source) =>
  ({
    yuque: "语雀文档",
    "seeyon-v5": "致远 V5 文档",
    agent: "Agent 沉淀",
    manual: "团队经验",
    "corpus-import": "语料导入",
    upload: "上传文档",
  })[source] ||
  source ||
  "知识库";
