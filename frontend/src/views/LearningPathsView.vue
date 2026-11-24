<script setup lang="ts">
import AppIcon from '@/components/AppIcon.vue'

const steps = [
  { title: 'Research brief', detail: 'Key ideas from the papers in your chat, with sources' },
  { title: 'Learning path', detail: 'A weekly plan, easiest first' },
  { title: 'Capstone project', detail: 'A portfolio project to build' },
  { title: 'Posts to publish', detail: 'LinkedIn, Substack and Notion drafts' },
]
</script>

<template>
  <div class="page">
    <header class="page-head">
      <h1>Learning paths</h1>
      <p>Turn a chat into a full plan: four steps, each built on the papers your answers cited.</p>
    </header>

    <ol class="steps" aria-label="What a learning path contains">
      <li v-for="(s, i) in steps" :key="s.title" class="step">
        <span class="step-n">Step {{ i + 1 }}</span>
        <span class="step-title">{{ s.title }}</span>
        <span class="step-detail">{{ s.detail }}</span>
      </li>
    </ol>

    <p class="alert alert-info">
      <AppIcon name="clock" />
      <span>
        Learning paths aren’t connected yet: the server doesn’t have an endpoint for them. Your chats and their sources
        are kept, so you’ll be able to turn any of them into a path once it’s ready.
      </span>
    </p>

    <div>
      <RouterLink :to="{ name: 'home' }" class="btn btn-outline">Ask a question meanwhile</RouterLink>
    </div>
  </div>
</template>

<style scoped>
.page { max-width: 980px; margin: 0 auto; padding: 32px clamp(16px, 4vw, 64px) 64px; display: flex; flex-direction: column; gap: 24px; }
.page-head { display: flex; flex-direction: column; gap: 8px; }
.page-head h1 { font-size: clamp(28px, 3vw, 38px); font-weight: 900; letter-spacing: -0.02em; }
.page-head p { max-width: 640px; color: var(--secondary); }

.steps { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(min(200px, 100%), 1fr)); gap: 12px; }
.step { display: flex; flex-direction: column; gap: 6px; padding: 16px; min-height: 112px; border-radius: 12px; border: 1px solid var(--line); background: var(--surface); }
.step-n { font-family: var(--mono); font-size: 12px; color: var(--dim); }
.step-title { font-size: 16px; font-weight: 900; color: var(--text); }
.step-detail { font-size: 13px; line-height: 1.5; color: var(--dim); }
</style>
