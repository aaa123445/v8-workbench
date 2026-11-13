<script setup>
import { ArrowRight, BookOpen } from "lucide-vue-next";
import HeroSection from "../components/site/HeroSection.vue";
import FeaturesSection from "../components/site/FeaturesSection.vue";
import WorkflowSection from "../components/site/WorkflowSection.vue";
import IntegrationsSection from "../components/site/IntegrationsSection.vue";
import FaqSection from "../components/site/FaqSection.vue";
import { hasAccess, currentUser } from "../composables/session";
</script>
<template>
  <div class="landing-page">
    <HeroSection />
    <div class="platform-strip site-container">
      <span>沉淀团队的每一类知识</span>
      <div>
        <span>技术开发</span><i /><span>运维部署</span><i /><span
          >产品与业务</span
        ><i /><span>项目实践</span><i /><span>团队规范</span>
      </div>
    </div>
    <FeaturesSection /><WorkflowSection /><IntegrationsSection /><FaqSection />
    <section class="site-cta-wrap site-container">
      <div class="site-cta">
        <span class="site-kicker">LESS GUESSWORK. MORE BUILDING.</span>
        <h2>把时间用在创造上，<br />让知识为你铺好下一步。</h2>
        <p>你的下一次开发，可以从已有的经验开始。</p>
        <div>
          <RouterLink
            :to="
              hasAccess ? '/workspace' : currentUser ? '/account' : '/register'
            "
            class="button primary large"
            >{{
              hasAccess
                ? "进入工作台"
                : currentUser
                  ? "查看账号状态"
                  : "注册并申请入网"
            }}<ArrowRight :size="17" /></RouterLink
          ><RouterLink to="/guide" class="button large"
            ><BookOpen :size="17" />阅读使用说明</RouterLink
          >
        </div>
      </div>
    </section>
  </div>
</template>
