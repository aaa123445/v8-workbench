<script setup>
import { focusMain } from "../composables/accessibility";
import SiteHeader from "../components/site/SiteHeader.vue";
import SiteFooter from "../components/site/SiteFooter.vue";
import "../styles/marketing.css";
</script>
<template>
  <div class="public-site">
    <a class="skip-link" href="#main" @click.prevent="focusMain"
      >跳转到主要内容</a
    ><SiteHeader />
    <main id="main" class="public-main" tabindex="-1"><slot /></main>
    <SiteFooter />
  </div>
</template>
