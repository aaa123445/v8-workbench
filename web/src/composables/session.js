import { ref, computed } from "vue";
import { api, post } from "../services/api";
import { apiKey, saveKey, authVersion, stats } from "./workspace";
export const currentUser = ref(null);
export const sessionReady = ref(false);
export const hasAccess = computed(
  () =>
    currentUser.value?.status === "approved" ||
    (!currentUser.value && !!apiKey.value),
);
export const isAdmin = computed(() =>
  currentUser.value
    ? currentUser.value.status === "approved" &&
      currentUser.value.role === "admin"
    : !!apiKey.value,
);
export const statusLabel = (status) =>
  ({
    pending: "待审批",
    approved: "已入网",
    rejected: "未通过",
    disabled: "已停用",
  })[status] || status;
export const roleLabel = (role) =>
  ({ reader: "只读成员", writer: "读写成员", admin: "管理员" })[role] || role;
let initializing;
export function loadSession() {
  if (!initializing)
    initializing = api("/auth/me", { key: "" })
      .then((data) => {
        currentUser.value = data.user;
        // Account login takes priority over previously saved browser API credentials.
        if (data.user && apiKey.value) saveKey("");
      })
      .catch((error) => {
        if (error.status !== 401) throw error;
        currentUser.value = null;
      })
      .finally(() => {
        sessionReady.value = true;
        authVersion.value++;
      });
  return initializing;
}
export async function refreshUser() {
  const data = await api("/auth/me", { key: "" });
  currentUser.value = data.user;
  authVersion.value++;
  return data.user;
}
export async function login(username, password) {
  const data = await post("/auth/login", { username, password }, { key: "" });
  currentUser.value = data.user;
  saveKey("");
  return data.user;
}
export async function logout() {
  await post("/auth/logout", {}, { key: "" });
  currentUser.value = null;
  stats.value = null;
  saveKey("");
}
export function passwordChanged() {
  currentUser.value = null;
  saveKey("");
}
