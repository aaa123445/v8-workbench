# UI template attribution

This frontend adapts portions of the following MIT-licensed Vue templates:

## Shadcn/Vue Landing Page Template

- Repository: https://github.com/leoMirandaa/shadcn-vue-landing-page
- Reference commit: `8578cba17b754f28316a78a289c2a5df6373335d`
- Copyright (c) 2024 Leopoldo Miranda
- License: [MIT](public/licenses/shadcn-vue-landing-page.txt)
- Adapted: Hero.vue's badge/gradient heading/dual CTA/product-preview structure;
  Features.vue's data-driven icon-card grid; HowItWorks.vue's step structure;
  FAQ.vue's question/answer data model and accordion presentation.
- Our changes: Chinese product copy, real workbench links, native accessible FAQ,
  interactive integration examples, locally rendered product illustration,
  and responsive CSS in place of the template's Tailwind classes and demo assets.

## Shadcn Vue Admin

- Repository: https://github.com/Whbbit1999/shadcn-vue-admin
- Reference commit: `10106074894c5edcea08ec516a51641b15344077`
- Copyright (c) 2024 Whbbit1999
- License: [MIT](public/licenses/shadcn-vue-admin.txt)
- Adapted: layouts/default.vue's sidebar/inset/sticky-header/main composition,
  app-sidebar/index.vue's header/content/footer organization,
  components/ui/card/Card.vue's data-slot card primitive, and neutral theme
  variables from assets/index.css.
- Our changes: Vue JavaScript/CSS modules, our existing session and API services,
  real navigation and data, mobile navigation and project-specific branding.

The full demo apps, sample customer data, external marketing assets and their
unneeded dependencies are not bundled. Our existing backend and account
permissions remain authoritative. Full license texts ship in the website's
`/static/licenses/` directory with every production build.

## TailAdmin Vue (workbench redesign)

- Repository: https://github.com/TailAdmin/vue-tailwind-admin-dashboard
- Reference commit: `66a320ed34f5b22b75255bc5fbe4656636b625e8`
- Copyright (c) 2026 TailAdmin
- License: [MIT](public/licenses/tailadmin-vue.txt)
- Adapted: AppSidebar.vue grouped navigation / compact mode, AppHeader.vue sticky
  search and shortcut composition, EcommerceMetrics.vue and MetricCard.vue's
  icon / value / description card structure; brand-blue and gray palette.
- Changes: JavaScript Vue components, Chinese knowledge-management workflows,
  existing authentication, accessible command search, responsive reading and
  editing layouts. Tailwind utility styles are translated into project CSS.
  No template demo data, analytics or external fonts are included.

## relation-graph (knowledge-chain visualization)

- Repository: https://github.com/seeksdream/relation-graph (now https://github.com/relation-graph/relation-graph).
- Installed package: `relation-graph-vue3` 2.2.11, MIT license.
- Copyright and full license: [relation-graph MIT](public/licenses/relation-graph.txt).
- Used: Vue 3 graph renderer, center layout, node dragging, canvas panning and zoom controls.
- Our adaptation: custom document cards, a quiet lavender knowledge workspace, explicit relation styling, independent-document state, accessible node buttons and separate optional related-reading list. Similarity suggestions never become graph edges automatically.

## StackHacker Chat (assistant conversation interface)

- Repository: https://github.com/stackhacker-ui/chat
- Reference commit: `edc0d30e54f3704543bc38ec55e76e228e672456`
- Copyright (c) 2025-2026 hirotaka
- License: [MIT](public/licenses/stackhacker-chat.txt)
- Adapted: ChatMessage.vue's left/right message and avatar composition,
  ChatPrompt.vue's composer and keyboard submission, and conversational welcome layout.
- Changes: Existing Vue app authentication, bounded server-side conversation context,
  knowledge retrieval, per-answer citations, error/retry/stop behavior and responsive CSS.
  No template backend, tracking, provider secrets or demo authentication are included.
