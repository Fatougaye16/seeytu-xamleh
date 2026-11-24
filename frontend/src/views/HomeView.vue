<script setup lang="ts">
import { useRouter } from 'vue-router'
import ChatComposer from '@/components/ChatComposer.vue'
import { useChatsStore } from '@/stores/chats'

const chats = useChatsStore()
const router = useRouter()

const examples = [
  'How do retrieval-augmented models decide when to search?',
  'What makes a vector database fast?',
  'Can small language models run well on a laptop GPU?',
]

function ask(question: string) {
  const id = chats.start(question)
  router.push({ name: 'chat', params: { id } })
}
</script>

<template>
  <div class="home">
    <div class="home-inner">
      <div class="intro">
        <span class="eyebrow intro-eyebrow">Ask the papers</span>
        <h1>What do you want to understand?</h1>
        <p>
          We find relevant research papers, read them, and answer with every claim linked to its source.
        </p>
      </div>

      <ChatComposer
        label="Your question"
        size="large"
        placeholder="e.g. How do retrieval-augmented models decide when to search?"
        autofocus
        @submit="ask"
      />

      <div class="examples">
        <h2 class="examples-label">Or try one of these</h2>
        <ul>
          <li v-for="q in examples" :key="q">
            <button type="button" class="chip" @click="ask(q)">{{ q }}</button>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<style scoped>
.home { min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 64px 24px; }
.home-inner { width: 100%; max-width: 760px; display: flex; flex-direction: column; gap: 32px; }

.intro { display: flex; flex-direction: column; align-items: center; gap: 12px; text-align: center; }
.intro-eyebrow { color: var(--accent-text); }
.intro h1 { font-size: clamp(30px, 3.4vw, 44px); line-height: 1.15; font-weight: 900; letter-spacing: -0.02em; text-wrap: balance; }
.intro p { max-width: 560px; font-size: 17px; color: var(--secondary); }

.examples { display: flex; flex-direction: column; align-items: center; gap: 12px; }
.examples-label { font-size: 13px; font-weight: 400; color: var(--dim); }
.examples ul { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; }
.chip {
  min-height: 44px; padding: 8px 16px; border-radius: var(--pill);
  border: 1px solid var(--line-strong); background: var(--surface); color: var(--secondary);
  font-size: 14px; text-align: left; cursor: pointer;
  transition: border-color var(--t), color var(--t);
}
.chip:hover { border-color: var(--accent); color: var(--text); }

@media (max-width: 899px) {
  .home { min-height: calc(100vh - 60px); align-items: flex-start; padding-top: 40px; }
}
</style>
