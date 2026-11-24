<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppIcon from '@/components/AppIcon.vue'
import AssistantMessage from '@/components/AssistantMessage.vue'
import ChatComposer from '@/components/ChatComposer.vue'
import SourceCard from '@/components/SourceCard.vue'
import { useChatsStore, type AssistantMessage as AssistantMsg } from '@/stores/chats'

const route = useRoute()
const router = useRouter()
const chats = useChatsStore()

const id = computed(() => String(route.params.id))
const conversation = computed(() => chats.get(id.value))
const busy = computed(() => chats.isBusy(id.value))

/** Which answer's sources the panel shows, and which citation is open. */
const selection = ref<{ messageId: string; n: number | null } | null>(null)
watch(id, () => (selection.value = null))

const answered = computed(() =>
  (conversation.value?.messages ?? []).filter(
    (m): m is AssistantMsg => m.role === 'assistant' && m.status === 'done' && !!m.sources?.length,
  ),
)
const panelMessage = computed(() => {
  const chosen = selection.value && answered.value.find((m) => m.id === selection.value!.messageId)
  return chosen ?? answered.value[answered.value.length - 1] ?? null
})
const activeN = computed(() =>
  selection.value && panelMessage.value && selection.value.messageId === panelMessage.value.id ? selection.value.n : null,
)

function selectCitation(messageId: string, n: number) {
  const same = selection.value?.messageId === messageId && selection.value.n === n
  selection.value = { messageId, n: same ? null : n }
  if (!same) {
    nextTick(() =>
      document.getElementById(`src-${messageId}-${n}`)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }),
    )
  }
}

function citationFor(m: AssistantMsg) {
  return selection.value?.messageId === m.id ? selection.value.n : null
}

// Keep the newest message in view as the thread grows.
const threadEnd = ref<HTMLElement | null>(null)
watch(
  () => conversation.value?.messages.length,
  () => nextTick(() => threadEnd.value?.scrollIntoView({ behavior: 'smooth', block: 'end' })),
  { immediate: true },
)

function send(question: string) {
  chats.followUp(id.value, question)
  selection.value = null
}

function remove() {
  if (!conversation.value) return
  if (!window.confirm(`Delete “${conversation.value.title}”? This can’t be undone.`)) return
  chats.remove(id.value)
  router.push({ name: 'home' })
}
</script>

<template>
  <div v-if="!conversation" class="missing">
    <h1>This chat doesn’t exist</h1>
    <p>It may have been deleted, or it was saved in a different browser.</p>
    <RouterLink :to="{ name: 'home' }" class="btn btn-primary">Start a new chat</RouterLink>
  </div>

  <div v-else class="conversation">
    <section class="thread" aria-label="Conversation">
      <header class="thread-head">
        <h1>{{ conversation.title }}</h1>
        <button type="button" class="btn btn-ghost btn-sm" @click="remove">
          <AppIcon name="trash" :size="15" /> Delete
        </button>
      </header>

      <template v-for="m in conversation.messages" :key="m.id">
        <div v-if="m.role === 'user'" class="user-row">
          <p class="user-bubble">{{ m.text }}</p>
        </div>
        <AssistantMessage
          v-else
          :message="m"
          :active-citation="citationFor(m)"
          @cite="(n) => selectCitation(m.id, n)"
          @stop="chats.stop(id)"
          @retry="chats.retry(id, m.id)"
        />
      </template>
      <div ref="threadEnd"></div>

      <div class="composer-dock">
        <ChatComposer
          label="Ask a follow-up"
          placeholder="Ask a follow-up…"
          :disabled="busy"
          disabled-hint="Wait for the current answer, or stop it."
          @submit="send"
        />
      </div>
    </section>

    <aside class="sources" aria-labelledby="sources-heading">
      <div class="sources-head">
        <h2 id="sources-heading">Sources</h2>
        <span v-if="panelMessage?.sources?.length" class="sources-count">
          {{ panelMessage.sources.length }} {{ panelMessage.sources.length === 1 ? 'paper' : 'papers' }}
        </span>
      </div>

      <p v-if="answered.length > 1 && panelMessage" class="sources-for">
        For: “{{ panelMessage.question }}”
      </p>

      <div v-if="panelMessage?.sources?.length" class="sources-list">
        <SourceCard
          v-for="s in panelMessage.sources"
          :id="`src-${panelMessage.id}-${s.number}`"
          :key="s.document_id"
          :source="s"
          :active="activeN === s.number"
          @toggle="selectCitation(panelMessage.id, s.number)"
        />
        <p class="sources-tip">Select a number in the answer to see the passage it came from.</p>
      </div>
      <p v-else-if="busy" class="sources-empty">Sources will appear here with the answer.</p>
      <p v-else class="sources-empty">No sources yet for this chat.</p>
    </aside>
  </div>
</template>

<style scoped>
.missing { min-height: 70vh; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; padding: 24px; text-align: center; }
.missing h1 { font-size: 26px; font-weight: 900; }
.missing p { color: var(--dim); margin-bottom: 8px; }

.conversation { min-height: 100vh; display: flex; flex-wrap: wrap; align-items: flex-start; }

.thread {
  flex: 999 1 520px; min-width: 0; min-height: 100vh;
  display: flex; flex-direction: column; gap: 28px;
  padding: 32px clamp(16px, 3vw, 48px) 0;
}
.thread-head { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; padding-bottom: 20px; border-bottom: 1px solid var(--line); }
.thread-head h1 { font-size: 22px; font-weight: 900; min-width: 0; overflow-wrap: anywhere; }

.user-row { display: flex; justify-content: flex-end; }
.user-bubble {
  max-width: min(560px, 90%); padding: 14px 18px; border-radius: 14px 14px 4px 14px;
  background: var(--tint-strong); color: var(--text); font-size: 16px; line-height: 1.55;
  white-space: pre-wrap; overflow-wrap: anywhere;
}

.composer-dock {
  position: sticky; bottom: 0; margin-top: auto; padding: 16px 0 24px;
  background: linear-gradient(to bottom, transparent, var(--bg) 24px);
}
.composer-dock > * { max-width: 720px; }

.sources {
  flex: 1 1 340px; min-width: 0;
  display: flex; flex-direction: column; gap: 14px;
  padding: 32px 20px;
  background: var(--surface); border-left: 1px solid var(--line);
  align-self: stretch;
}
.sources-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.sources-head h2 { font-size: 16px; font-weight: 900; }
.sources-count { font-size: 13px; color: var(--dim); }
.sources-for { font-size: 13px; color: var(--dim); overflow-wrap: anywhere; }
.sources-list { display: flex; flex-direction: column; gap: 12px; }
.sources-tip, .sources-empty { font-size: 13px; color: var(--dim); }

@media (min-width: 1200px) {
  .sources { position: sticky; top: 0; height: 100vh; overflow-y: auto; align-self: flex-start; }
}
@media (max-width: 1199px) {
  .sources { border-left: 0; border-top: 1px solid var(--line); }
  .composer-dock { position: static; }
}
</style>
