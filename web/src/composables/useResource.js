import { ref, watch } from "vue";
import { authVersion } from "./workspace";
// A sequence guards against outdated responses after key or parameter changes.
export function useResource(loader, dependencies = []) {
  const data = ref(null),
    loading = ref(false),
    error = ref("");
  let sequence = 0;
  async function reload() {
    const current = ++sequence;
    loading.value = true;
    error.value = "";
    data.value = null;
    try {
      const result = await loader();
      if (current === sequence) data.value = result;
    } catch (e) {
      if (current === sequence) error.value = e.message;
    } finally {
      if (current === sequence) loading.value = false;
    }
  }
  watch([authVersion, ...dependencies], reload, { immediate: true });
  return { data, loading, error, reload };
}
