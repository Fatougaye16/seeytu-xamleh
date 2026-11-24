<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import AppIcon from './AppIcon.vue'
import AnswerBody from './AnswerBody.vue'
import type { AssistantMessage } from '@/stores/chats'
import { answerToPlainText } from '@/lib/answer'

const props = defineProps<{
  message: AssistantMessage
  /** Citation selected in the sources panel, if it belongs to this message. */
  activeCitation: number | null
}>()
const emit = defineEmits<{ cite: [n: number]; stop: []; retry: [] }>()

// Elapsed timer while pending — the backend doesn't stream progress yet, so time is the honest signal.
const now = ref(Date.now())
let timer: number | undefined
watch(
  () => props.message.status,
  (status) => {
    window.clearInterval(timer)
    if (status === 'pending') timer = window.setInterval(() => (now.value = Date.now()), 1000)
  },
  { immediate: true },
)
onBeforeUnmount(() => window.clearInterval(timer))

const elapsed = computed(() => Math.max(0, Math.round((now.value - props.message.startedAt) / 1000)))
const duration = computed(() => ((props.message.durationMs ?? 0) / 1000).toFixed(1))
const sources = computed(() => props.message.sources ?? [])
const validCitations = computed(() => sources.value.map((s) => s.number))
const abstractOnly = computed(() => sources.value.filter((s) => s.content_type === 'abstract').map((s) => s.number))

const copied = ref(false)
async function copy() {
  try {
    await navigator.clipboard.writeText(answerToPlainText(props.message.answer ?? '', sources.value))
    copied.value = true
    window.setTimeout(() => (copied.value = false), 2000)
  } catch {
    /* clipboard blocked: nothing useful to do */
  }
}
</script>

<template>
  <article class="assistant" :aria-label="message.status === 'pending' ? 'Answer in progress' : 'Answer'">
    <!-- Pending -->
    <div v-if="message.status === 'pending'" class="pending" role="status" aria-live="polite">
      <div class="pending-line">
        <span class="pulse-dot" aria-hidden="true"></span>
        <span class="pending-text">
          {{ elapsed < 8 ? 'Looking for relevant papers…' : 'Reading papers and writing the answer…' }}
        </span>
        <span class="pending-time">{{ elapsed }} s</span>
      </div>
      <p v-if="elapsed >= 20" class="pending-hint">
        New topics take longer: papers are downloaded and read before answering.
      </p>
      <div class="skeleton" style="height: 14px; width: 92%"></div>
      <div class="skeleton" style="height: 14px; width: 78%"></div>
      <div class="skeleton" style="height: 14px; width: 55%"></div>
      <div>
        <button type="button" class="btn btn-ghost btn-sm" @click="emit('stop')">
          <AppIcon name="stop" :size="14" /> Stop
        </button>
      </div>
    </div>

    <!-- Error / stopped -->
    <div v-else-if="message.status === 'error' || message.status === 'stopped'" class="failed">
      <p v-if="message.status === 'error'" class="alert alert-error" role="alert">
        <AppIcon name="alert" />
        <span>{{ message.error || 'Something went wrong while answering.' }}</span>
      </p>
      <p v-else class="alert alert-info">
        <AppIcon name="info" />
        <span>You stopped this answer.</span>
      </p>
      <div>
        <button type="button" class="btn btn-ghost btn-sm" @click="emit('retry')">
          <AppIcon name="refresh" :size="15" /> Try again
        </button>
      </div>
    </div>

    <!-- Done -->
    <template v-else>
      <p class="process">
        <AppIcon name="check" :size="15" :stroke-width="2.4" />
        Answered in {{ duration }} s from {{ sources.length }} {{ sources.length === 1 ? 'paper' : 'papers' }}
      </p>

      <AnswerBody
        :answer="message.answer ?? ''"
        :valid-citations="validCitations"
        :active-citation="activeCitation"
        @cite="(n) => emit('cite', n)"
      />

      <p v-if="sources.length" class="alert alert-info">
        <AppIcon name="info" />
        <span>
          Answered only from the {{ sources.length }} {{ sources.length === 1 ? 'paper' : 'papers' }} listed under Sources.
          <template v-if="abstractOnly.length">
            {{ abstractOnly.length === 1 ? `Source ${abstractOnly[0]} was` : `Sources ${abstractOnly.join(', ')} were` }}
            read from the abstract only, so check the full paper before relying on it.
          </template>
          <template v-else>Check the passages before you rely on it.</template>
        </span>
      </p>

      <div class="actions">
        <button type="button" class="btn btn-ghost btn-sm" @click="copy">
          <AppIcon :name="copied ? 'check' : 'copy'" :size="15" />
          {{ copied ? 'Copied' : 'Copy with sources' }}
        </button>
      </div>
    </template>
  </article>
</template>

<style scoped>
.assistant { display: flex; flex-direction: column; gap: 16px; max-width: 720px; }

.pending { display: flex; flex-direction: column; gap: 12px; }
.pending-line { display: flex; align-items: center; gap: 10px; font-size: 14px; }
.pending-text { color: var(--text); font-weight: 700; }
.pending-time { font-family: var(--mono); font-size: 12px; color: var(--dim); }
.pending-hint { font-size: 14px; color: var(--dim); }

.failed { display: flex; flex-direction: column; gap: 10px; }

.process { display: inline-flex; align-items: center; gap: 8px; font-size: 14px; color: var(--dim); }
.process :deep(svg) { color: var(--accent); }

.actions { display: flex; flex-wrap: wrap; gap: 8px; }
</style>
