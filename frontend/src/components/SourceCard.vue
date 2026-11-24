<script setup lang="ts">
import { computed } from 'vue'
import AppIcon from './AppIcon.vue'
import type { Source } from '@/api/rag'

const props = defineProps<{ source: Source; active: boolean }>()
const emit = defineEmits<{ toggle: [] }>()

const year = computed(() => props.source.published?.slice(0, 4))
const meta = computed(() => [props.source.authors, year.value].filter(Boolean).join(' · '))
const doiUrl = computed(() => {
  const doi = props.source.doi
  if (!doi) return null
  return doi.startsWith('http') ? doi : `https://doi.org/${doi}`
})
const paperUrl = computed(() => props.source.url ?? doiUrl.value)
const content = computed(() => {
  if (props.source.content_type === 'full_text') return { label: 'Full text', cls: 'tag-full' }
  if (props.source.content_type === 'abstract') return { label: 'Abstract only', cls: 'tag-abs' }
  return null
})
const panelId = computed(() => `source-${props.source.number}-details`)
</script>

<template>
  <article class="source" :class="{ 'is-active': active }" :aria-label="`Source ${source.number}`">
    <button
      type="button"
      class="source-head"
      :aria-expanded="active"
      :aria-controls="panelId"
      @click="emit('toggle')"
    >
      <span class="badge">{{ source.number }}</span>
      <span class="source-text">
        <span class="source-title">{{ source.title || 'Untitled paper' }}</span>
        <span v-if="meta" class="source-meta">{{ meta }}</span>
      </span>
    </button>

    <div v-if="content" class="source-tags">
      <span class="tag" :class="content.cls">{{ content.label }}</span>
    </div>

    <div v-if="active" :id="panelId" class="source-details">
      <blockquote v-if="source.passage" class="passage">{{ source.passage }}</blockquote>
      <p v-else class="passage-missing">The passage used isn’t available for this answer.</p>
      <div v-if="paperUrl || doiUrl" class="source-links">
        <a v-if="paperUrl" :href="paperUrl" target="_blank" rel="noopener noreferrer">
          Open paper <AppIcon name="external" :size="14" />
          <span class="visually-hidden">(opens in a new tab)</span>
        </a>
        <a v-if="doiUrl && doiUrl !== paperUrl" :href="doiUrl" target="_blank" rel="noopener noreferrer">
          DOI <AppIcon name="external" :size="14" />
          <span class="visually-hidden">(opens in a new tab)</span>
        </a>
      </div>
    </div>
  </article>
</template>

<style scoped>
.source {
  display: flex; flex-direction: column; gap: 12px;
  padding: 16px; border-radius: 12px;
  border: 1px solid var(--line); background: transparent;
  transition: border-color var(--t), background var(--t);
}
.source:hover { border-color: var(--line-strong); }
.source.is-active { border-color: var(--accent); background: var(--tint); }

.source-head {
  display: flex; gap: 12px; align-items: flex-start; width: 100%;
  padding: 0; border: 0; background: transparent; text-align: left; cursor: pointer;
}
.badge {
  flex: none; width: 28px; height: 28px; border-radius: var(--r);
  display: flex; align-items: center; justify-content: center;
  font-family: var(--mono); font-size: 13px; font-weight: 500;
  background: var(--tint); color: var(--accent-text);
}
.is-active .badge { background: var(--accent); color: var(--on-accent); }
.source-text { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.source-title { font-size: 15px; font-weight: 700; line-height: 1.35; color: var(--text); }
.source-meta { font-size: 13px; color: var(--dim); }

.source-tags, .source-details, .source-links { padding-left: 40px; }
.source-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.source-details { display: flex; flex-direction: column; gap: 10px; }
.passage {
  margin: 0; padding: 12px 14px; border-radius: var(--r);
  background: var(--surface); font-size: 14px; line-height: 1.6; color: var(--body);
  max-height: 240px; overflow-y: auto;
}
.passage-missing { font-size: 14px; color: var(--dim); }
.source-links { display: flex; flex-wrap: wrap; gap: 16px; padding-left: 0; font-size: 14px; font-weight: 700; }
.source-links a { display: inline-flex; align-items: center; gap: 4px; }
</style>
