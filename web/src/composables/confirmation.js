import { shallowRef } from "vue";
export const confirmation = shallowRef(null);
let settle;
export function confirmAction({
  title = "确认操作",
  message = "",
  confirmLabel = "确认",
  danger = false,
} = {}) {
  if (settle) settle(false);
  return new Promise((resolve) => {
    settle = resolve;
    confirmation.value = { title, message, confirmLabel, danger };
  });
}
export function resolveConfirmation(value) {
  const resolve = settle;
  settle = null;
  confirmation.value = null;
  resolve?.(value);
}

export const ask = (message) =>
  confirmAction({
    title: "确认操作",
    message,
    confirmLabel: "确认",
    danger: true,
  });
