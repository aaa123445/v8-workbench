<script setup>
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
  onErrorCaptured,
} from "vue";
import RelationGraph from "relation-graph-vue3";
import {
  FileText,
  Maximize,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Move,
} from "lucide-vue-next";
const props = defineProps({
  graph: { type: Object, required: true },
  selected: String,
  globalView: Boolean,
});
const emit = defineEmits(["select"]);
const canvas = ref(null),
  ready = ref(false),
  failure = ref("");
const colors = ["#7963d2", "#3985a5", "#27977e", "#be8543", "#bd638e"];
const options = {
  debug: false,
  allowShowMiniToolBar: false,
  allowShowZoomMenu: false,
  allowShowRefreshButton: false,
  allowShowDownloadButton: false,
  allowShowFullscreenMenu: false,
  defaultNodeShape: 1,
  defaultNodeWidth: 176,
  defaultNodeHeight: 76,
  defaultNodeColor: "transparent",
  defaultNodeBorderWidth: 0,
  defaultNodeBorderColor: "transparent",
  defaultLineColor: "#c6bedc",
  defaultLineFontColor: "#8b82a0",
  defaultLineWidth: 1.5,
  defaultLineShape: 4,
  defaultJunctionPoint: "border",
  defaultShowLineLabel: true,
  disableNodeClickEffect: true,
  disableLineClickEffect: true,
  moveToCenterWhenRefresh: true,
  zoomToFitWhenRefresh: true,
  useAnimationWhenRefresh: false,
  backgroundColor: "transparent",
  layouts: [
    {
      layoutName: props.globalView ? "circle" : "center",
      distance_coefficient: 0.85,
      levelDistance: "210,190,170",
    },
  ],
};
const categoryMap = computed(() =>
  Object.fromEntries(
    (props.graph.categories || []).map((c, i) => [
      c.id,
      { ...c, color: colors[i % colors.length] },
    ]),
  ),
);
let generation = 0,
  observer,
  timeout;
function markFailure() {
  ready.value = false;
  failure.value = "图谱未能正常显示，可以重新布局或使用下方关系列表。";
}
onErrorCaptured(() => {
  markFailure();
  return false;
});
async function draw() {
  const current = ++generation;
  await nextTick();
  if (!canvas.value) {
    markFailure();
    return;
  }
  ready.value = false;
  failure.value = "";
  clearTimeout(timeout);
  timeout = setTimeout(() => {
    if (current === generation && !ready.value) markFailure();
  }, 10000);
  const validIds = new Set(props.graph.nodes.map((n) => n.id));
  const edges = props.graph.edges.filter(
    (e) =>
      ["manual", "reference"].includes(e.origin) &&
      validIds.has(e.source_id) &&
      validIds.has(e.target_id),
  );
  const linked = new Set(edges.flatMap((e) => [e.source_id, e.target_id]));
  try {
    await instance().setJsonData({
      rootId: props.graph.center,
      nodes: props.graph.nodes
        .filter((n) => n.id === props.graph.center || linked.has(n.id))
        .map((n) => ({
          id: n.id,
          text: n.title,
          data: {
            ...n,
            category: categoryMap.value[n.category_id]?.name || "知识文档",
            color: categoryMap.value[n.category_id]?.color || colors[0],
            isCenter: !props.globalView && n.id === props.graph.center,
          },
          width: 176,
          height: 76,
          color: "transparent",
          borderWidth: 0,
        })),
      lines: edges.map((e) => ({
        id: e.id,
        from: e.source_id,
        to: e.target_id,
        text: e.label,
        color: e.origin === "manual" ? "#a99acb" : "#c0c9d4",
        dashType: e.origin === "reference" ? 1 : 0,
        showEndArrow: true,
        lineWidth: e.origin === "manual" ? 1.8 : 1.3,
        data: e,
      })),
    });
    if (current === generation) {
      ready.value = true;
      clearTimeout(timeout);
    }
  } catch (e) {
    if (current === generation) failure.value = "图谱暂时无法加载，请重试";
  }
}
function instance() {
  return canvas.value?.getInstance();
}
function fit() {
  instance()?.moveToCenter();
  instance()?.zoomToFit();
}
function zoom(amount) {
  instance()?.zoom(amount);
}
function select(node) {
  emit("select", node.id);
  return false;
}
watch(() => props.graph, draw);
onMounted(() => {
  draw();
  observer = new ResizeObserver(() => canvas.value?.onGraphResize());
  const el = canvas.value?.$el;
  if (el) observer.observe(el);
});
onBeforeUnmount(() => {
  generation++;
  observer?.disconnect();
  clearTimeout(timeout);
  instance()?.stopAutoLayout?.();
});
</script>
<template>
  <div class="kb-canvas-shell">
    <div class="kb-canvas-toolbar">
      <span><i />关系图谱</span>
      <div>
        <button type="button" aria-label="缩小图谱" @click="zoom(-15)">
          <ZoomOut :size="16" /></button
        ><button type="button" aria-label="放大图谱" @click="zoom(15)">
          <ZoomIn :size="16" /></button
        ><span /><button type="button" aria-label="适应图谱" @click="fit">
          <Maximize :size="16" /></button
        ><button type="button" aria-label="重新布局" @click="draw">
          <RotateCcw :size="15" />
        </button>
      </div>
    </div>
    <div
      class="knowledge-graph"
      role="img"
      aria-label="知识关系图谱"
      :aria-busy="!ready"
    >
      <RelationGraph ref="canvas" :options="options" :on-node-click="select">
        <template #node="{ node }"
          ><button
            type="button"
            :class="[
              'kb-graph-card',
              { selected: selected === node.id, center: node.data.isCenter },
            ]"
            :style="{ '--node-accent': node.data.color }"
            :aria-label="'选择知识：' + node.text"
            :aria-pressed="selected === node.id"
            @click.stop="emit('select', node.id)"
          >
            <span class="kb-graph-card-top"
              ><FileText :size="13" /><small>{{ node.data.category }}</small
              ><i v-if="node.data.isCenter">当前</i></span
            ><strong :title="node.text">{{ node.text }}</strong>
          </button></template
        >
      </RelationGraph>
    </div>
    <div v-if="failure" class="kb-canvas-error" role="alert">
      {{ failure }}<button class="text-link" @click="draw">重试</button>
    </div>
    <div class="kb-canvas-hint">
      <Move :size="12" />拖拽移动 · 滚轮缩放 · 点击查看知识
    </div>
  </div>
</template>
<style>
.kb-canvas-shell {
  height: 570px;
  position: relative;
  overflow: hidden;
  border-radius: 14px;
  background:
    radial-gradient(ellipse at 50% 45%, #eeebf7a3, transparent 65%),
    radial-gradient(#c9c5d773 0.7px, transparent 0.7px);
  background-size:
    auto,
    20px 20px;
  background-color: #faf9fc;
  border: 1px solid #ece8f2;
}
.kb-canvas-shell .knowledge-graph {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  min-height: 0;
  background: none;
}
.kb-canvas-toolbar {
  position: absolute;
  top: 17px;
  left: 18px;
  right: 18px;
  z-index: 60;
  display: flex;
  justify-content: space-between;
  align-items: center;
  pointer-events: none;
}
.kb-canvas-toolbar > span {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 11px;
  color: #847b95;
}
.kb-canvas-toolbar > span i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #a08bc9;
}
.kb-canvas-toolbar > div {
  display: flex;
  align-items: center;
  gap: 3px;
  padding: 4px;
  background: #ffffffed;
  border: 1px solid #e9e4ef;
  border-radius: 10px;
  box-shadow: 0 4px 15px #3d254208;
  pointer-events: auto;
}
.kb-canvas-toolbar button {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  background: none;
  border: 0;
  border-radius: 6px;
  color: #797086;
  cursor: pointer;
}
.kb-canvas-toolbar button:hover {
  color: #7552b8;
  background: #f1ecfa;
}
.kb-canvas-toolbar div > span {
  height: 17px;
  width: 1px;
  background: #ece7f0;
  margin: 0 3px;
}
.kb-canvas-hint {
  position: absolute;
  bottom: 16px;
  left: 18px;
  font-size: 10px;
  color: #98909f;
  display: flex;
  gap: 6px;
  align-items: center;
  pointer-events: none;
}
.kb-canvas-error {
  position: absolute;
  inset: 80px 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  background: #faf9fc;
  color: #667085;
}
.kb-graph-card {
  width: 176px;
  height: 76px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  justify-content: center;
  text-align: left;
  padding: 12px 14px;
  background: #fff;
  border: 1px solid #e9e4ef;
  border-radius: 12px;
  color: #534b60;
  box-shadow: 0 4px 12px #48386009;
  cursor: grab;
  font-family: inherit;
  transition:
    border-color 0.15s,
    box-shadow 0.15s;
}
.kb-graph-card:hover {
  border-color: #c6b5df;
  box-shadow: 0 5px 15px #5d437514;
}
.kb-graph-card.selected {
  border-color: var(--node-accent);
  box-shadow:
    0 0 0 3px #a087c71c,
    0 6px 18px #604b7712;
}
.kb-graph-card.center {
  background: #fcfaff;
}
.kb-graph-card-top {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 7px;
  color: var(--node-accent);
}
.kb-graph-card-top small {
  font-size: 10px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.kb-graph-card-top i {
  font-size: 8px;
  font-style: normal;
  margin-left: auto;
  background: #ede7f7;
  border-radius: 4px;
  padding: 1px 4px;
  color: #8d72b9;
}
.kb-graph-card strong {
  font-size: 11px;
  font-weight: 550;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.5;
}
.kb-canvas-shell .relation-graph .rel-map {
  background: transparent !important;
}
.kb-canvas-shell .relation-graph .rel-node {
  box-shadow: none !important;
  border: 0 !important;
  background: transparent !important;
}
.kb-canvas-shell .relation-graph .c-rg-line-text {
  font-size: 10px !important;
}
.kb-canvas-shell .relation-graph .rel-node-checked {
  box-shadow: none !important;
}
@media (max-width: 800px) {
  .kb-canvas-shell {
    height: 420px;
  }
  .kb-canvas-toolbar {
    top: 12px;
    left: 12px;
    right: 12px;
  }
  .kb-canvas-hint {
    font-size: 9px;
    left: 12px;
  }
}
</style>
