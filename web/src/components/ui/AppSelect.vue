<script setup>
import {
  ref,
  useSlots,
  useId,
  nextTick,
  onBeforeUnmount,
  watch,
  Fragment,
  Text,
} from "vue";
import { ChevronDown, Check, Search } from "lucide-vue-next";
defineOptions({ inheritAttrs: false });
const props = defineProps({
  modelValue: [String, Number, Boolean],
  modelModifiers: { type: Object, default: () => ({}) },
  disabled: Boolean,
  placeholder: { type: String, default: "请选择" },
});
const emit = defineEmits(["update:modelValue", "change"]);
const slots = useSlots(),
  id = useId();
const trigger = ref(null),
  panel = ref(null),
  search = ref(null),
  open = ref(false),
  query = ref(""),
  active = ref(-1);
const position = ref({}),
  listHeight = ref(280);
// Preserve typed values and conditional/looped option slots at the call site.
function textOf(node) {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(textOf).join("");
  return node?.type === Text || typeof node?.children === "string"
    ? String(node.children)
    : textOf(node?.children || []);
}
function optionsOf(nodes) {
  return nodes.flatMap((node) => {
    if (node.type === Fragment) return optionsOf(node.children || []);
    if (node.type !== "option") return [];
    const label = textOf(node.children).trim();
    return [
      {
        value: node.props?.value ?? label,
        label,
        disabled:
          node.props?.disabled !== undefined && node.props.disabled !== false,
      },
    ];
  });
}
// Slot content is read during rendering so async option lists remain reactive.
let renderedOptions = [];
function syncOptions() {
  renderedOptions = optionsOf(slots.default?.() || []);
  return renderedOptions.length;
}
const options = () => renderedOptions;
const filtered = () =>
  options().filter(
    (item) =>
      !query.value ||
      item.label.toLocaleLowerCase().includes(query.value.toLocaleLowerCase()),
  );
const selected = () =>
  options().find((item) => String(item.value) === String(props.modelValue));
const searchable = () => options().length > 8;
function place() {
  if (!trigger.value) return;
  const rect = trigger.value.getBoundingClientRect(),
    margin = 10;
  const width = Math.min(
    Math.max(rect.width, 220),
    window.innerWidth - margin * 2,
  );
  const below = window.innerHeight - rect.bottom - margin - 6,
    above = rect.top - margin - 6;
  const up = below < 240 && above > below;
  const available = Math.max(80, up ? above : below);
  listHeight.value = Math.min(280, available - (searchable() ? 55 : 12));
  position.value = {
    width: `${width}px`,
    left: `${Math.max(margin, Math.min(rect.left, window.innerWidth - width - margin))}px`,
    ...(up
      ? { bottom: `${window.innerHeight - rect.top + 6}px` }
      : { top: `${rect.bottom + 6}px` }),
    transformOrigin: up ? "bottom center" : "top center",
  };
}
function close(restore = false) {
  open.value = false;
  if (restore) trigger.value?.focus();
}
async function reveal() {
  if (props.disabled) return;
  query.value = "";
  active.value = options().findIndex(
    (item) => String(item.value) === String(props.modelValue) && !item.disabled,
  );
  if (active.value < 0)
    active.value = options().findIndex((item) => !item.disabled);
  place();
  open.value = true;
  await nextTick();
  if (searchable()) search.value?.focus();
  scrollActive();
}
function scrollActive() {
  nextTick(() =>
    document
      .getElementById(`${id}-option-${active.value}`)
      ?.scrollIntoView({ block: "nearest" }),
  );
}
function choose(item) {
  if (!item || item.disabled) return;
  let value = item.value;
  if (
    props.modelModifiers.number &&
    value !== "" &&
    Number.isFinite(Number(value))
  )
    value = Number(value);
  emit("update:modelValue", value);
  emit("change", { target: { value } });
  close(true);
}
function move(step) {
  const items = filtered();
  for (let offset = 1; offset <= items.length; offset++) {
    const index = (active.value + step * offset + items.length) % items.length;
    if (!items[index].disabled) {
      active.value = index;
      scrollActive();
      break;
    }
  }
}
let typed = "",
  typeTimer;
function keydown(event) {
  if (event.key === "Tab") {
    close();
    return;
  }
  if (event.key === "Escape" && open.value) {
    event.preventDefault();
    event.stopPropagation();
    close(true);
    return;
  }
  if (
    ["ArrowDown", "ArrowUp", "Enter", " ", "Home", "End"].includes(event.key) &&
    event.target !== search.value
  ) {
    event.preventDefault();
    if (!open.value) {
      reveal();
      return;
    }
    if (event.key === "Enter" || event.key === " ")
      choose(filtered()[active.value]);
    else if (event.key === "Home" || event.key === "End") {
      const items = filtered();
      active.value =
        event.key === "Home"
          ? items.findIndex((i) => !i.disabled)
          : items.findLastIndex((i) => !i.disabled);
      scrollActive();
    } else move(event.key === "ArrowDown" ? 1 : -1);
  } else if (
    event.target === search.value &&
    ["ArrowDown", "ArrowUp", "Enter"].includes(event.key)
  ) {
    event.preventDefault();
    if (event.key === "Enter") choose(filtered()[active.value]);
    else move(event.key === "ArrowDown" ? 1 : -1);
  } else if (
    open.value &&
    event.target !== search.value &&
    event.key.length === 1
  ) {
    event.preventDefault();
    clearTimeout(typeTimer);
    typed += event.key.toLocaleLowerCase();
    active.value = filtered().findIndex(
      (i) => !i.disabled && i.label.toLocaleLowerCase().startsWith(typed),
    );
    scrollActive();
    typeTimer = setTimeout(() => {
      typed = "";
    }, 600);
  }
}
function outside(event) {
  if (
    !trigger.value?.contains(event.target) &&
    !panel.value?.contains(event.target)
  )
    close();
}
function focusOutside(event) {
  if (open.value) outside(event);
}
function onScroll(event) {
  if (!panel.value?.contains(event.target)) place();
}
watch(query, () => {
  active.value = filtered().findIndex((i) => !i.disabled);
  scrollActive();
});
watch(
  () => props.disabled,
  (value) => {
    if (value) close();
  },
);
watch(open, (value) => {
  for (const [event, handler, capture] of [
    ["pointerdown", outside, true],
    ["focusin", focusOutside, true],
    ["scroll", onScroll, true],
  ]) {
    document[value ? "addEventListener" : "removeEventListener"](
      event,
      handler,
      capture,
    );
  }
  window[value ? "addEventListener" : "removeEventListener"]("resize", place);
});
onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", outside, true);
  document.removeEventListener("focusin", focusOutside, true);
  document.removeEventListener("scroll", onScroll, true);
  window.removeEventListener("resize", place);
  clearTimeout(typeTimer);
});
</script>
<template>
  <button
    ref="trigger"
    v-bind="$attrs"
    :data-option-count="syncOptions()"
    type="button"
    role="combobox"
    class="app-select"
    :class="{ 'is-open': open }"
    :disabled="disabled"
    aria-haspopup="listbox"
    :aria-expanded="open"
    :aria-controls="open ? `${id}-list` : undefined"
    :aria-activedescendant="
      open && active >= 0 ? `${id}-option-${active}` : undefined
    "
    @click="open ? close() : reveal()"
    @keydown="keydown"
  >
    <span class="app-select-value" :class="{ 'is-placeholder': !selected() }">{{
      selected()?.label || placeholder
    }}</span>
    <ChevronDown class="app-select-chevron" :size="15" />
  </button>
  <Teleport to="body">
    <Transition name="select-popover">
      <div
        v-if="open"
        ref="panel"
        class="app-select-panel"
        :style="position"
        @keydown="keydown"
      >
        <div v-if="searchable()" class="app-select-search">
          <Search :size="15" /><input
            ref="search"
            v-model="query"
            aria-label="筛选选项"
            placeholder="输入关键词筛选…"
            autocomplete="off"
            :aria-controls="`${id}-list`"
            :aria-activedescendant="
              active >= 0 ? `${id}-option-${active}` : undefined
            "
          />
        </div>
        <div
          :id="`${id}-list`"
          role="listbox"
          :aria-label="$attrs['aria-label'] || '可选项'"
          class="app-select-options"
          :style="{ maxHeight: `${listHeight}px` }"
        >
          <div
            v-for="(item, index) in filtered()"
            :id="`${id}-option-${index}`"
            :key="String(item.value)"
            role="option"
            :aria-selected="String(item.value) === String(modelValue)"
            :aria-disabled="item.disabled || undefined"
            class="app-select-option"
            :class="{
              'is-active': active === index,
              'is-selected': String(item.value) === String(modelValue),
            }"
            :data-value="item.value"
            @pointermove="!item.disabled && (active = index)"
            @pointerdown.prevent
            @click="choose(item)"
          >
            <span>{{ item.label }}</span><Check
              v-if="String(item.value) === String(modelValue)"
              :size="15"
            />
          </div>
          <div v-if="!filtered().length" class="app-select-empty">
            没有匹配的选项
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
