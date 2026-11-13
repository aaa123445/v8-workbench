<script setup>
// Adapted from Whbbit1999/shadcn-vue-admin Card.vue (MIT).
// See web/THIRD_PARTY_NOTICES.md and public/licenses/shadcn-vue-admin.txt.
defineProps({ as: { type: String, default: "div" } });
</script>
<template>
  <component :is="as" data-slot="card" class="surface-card"><slot /></component>
</template>
