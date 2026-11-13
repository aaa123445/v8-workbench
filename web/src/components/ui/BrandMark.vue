<script setup>
defineProps({ compact: Boolean });
</script>
<template>
  <span class="brand-identity"
    ><span class="brand-symbol">K<span>B</span><i /></span
    ><span v-if="!compact" class="brand-name"
      ><strong>TeamKB</strong><small>团队知识共享平台</small></span
    ></span
  >
</template>
