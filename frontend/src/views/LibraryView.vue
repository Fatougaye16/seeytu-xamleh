<script setup lang="ts">
import { computed, ref } from 'vue'
import AppIcon from '@/components/AppIcon.vue'
import { useChatsStore } from '@/stores/chats'

const chats = useChatsStore()

type Filter = 'all' | 'full_text' | 'abstract'
const query = ref('')
const filter = ref<Filter>('all')

const hasContentInfo = computed(() => chats.library.some((p) => p.source.content_type))

const papers = computed(() => {
  const q = query.value.trim().toLowerCase()
  return chats.library.filter(({ source }) => {
    if (filter.value !== 'all' && source.content_type !== filter.value) return false
    if (!q) return true
    return `${source.title ?? ''} ${source.authors ?? ''}`.toLowerCase().includes(q)
  })
})

const filters: { id: Filter; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'full_text', label: 'Full text' },
  { id: 'abstract', label: 'Abstract only' },
]

function paperUrl(s: { url?: string | null; doi?: string | null }) {
  if (s.url) return s.url
  if (s.doi) return s.doi.startsWith('http') ? s.doi : `https://doi.org/${s.doi}`
  return null
}
</script>

<template>
  <div class="page">
    <header class="page-head">
      <h1>Library</h1>
      <p>Every paper cited in your chats, in one place. It’s kept in this browser for your account.</p>
    </header>

    <div v-if="!chats.library.length" class="empty">
      <span class="empty-icon"><AppIcon name="library" :size="26" /></span>
      <h2>No papers yet</h2>
      <p>Ask a question and the papers behind the answer will be collected here.</p>
      <RouterLink :to="{ name: 'home' }" class="btn btn-primary">Ask a question</RouterLink>
    </div>

    <template v-else>
      <div class="toolbar">
        <div class="search">
          <label for="lib-search" class="visually-hidden">Search papers</label>
          <AppIcon name="search" :size="16" class="search-icon" />
          <input id="lib-search" v-model="query" class="input" type="search" placeholder="Search titles and authors" />
        </div>
        <div v-if="hasContentInfo" class="filters" role="group" aria-label="Filter by what was read">
          <button
            v-for="f in filters"
            :key="f.id"
            type="button"
            class="filter"
            :class="{ 'is-on': filter === f.id }"
            :aria-pressed="filter === f.id"
            @click="filter = f.id"
          >{{ f.label }}</button>
        </div>
      </div>

      <p class="count" role="status">
        Showing {{ papers.length }} of {{ chats.library.length }} {{ chats.library.length === 1 ? 'paper' : 'papers' }}
      </p>

      <ul v-if="papers.length" class="list">
        <li v-for="p in papers" :key="p.source.document_id" class="paper">
          <div class="paper-main">
            <a v-if="paperUrl(p.source)" :href="paperUrl(p.source)!" target="_blank" rel="noopener noreferrer" class="paper-title">
              {{ p.source.title || 'Untitled paper' }}
              <AppIcon name="external" :size="14" />
              <span class="visually-hidden">(opens in a new tab)</span>
            </a>
            <span v-else class="paper-title">{{ p.source.title || 'Untitled paper' }}</span>
            <span class="paper-meta">
              {{ [p.source.authors, p.source.published?.slice(0, 4)].filter(Boolean).join(' · ') }}
            </span>
          </div>
          <div class="paper-tags">
            <span v-if="p.source.content_type === 'full_text'" class="tag tag-full">Full text</span>
            <span v-else-if="p.source.content_type === 'abstract'" class="tag tag-abs">Abstract only</span>
          </div>
          <div class="paper-used">
            <span class="used-label">Used in</span>
            <RouterLink
              v-for="c in p.conversations.slice(0, 2)"
              :key="c.id"
              :to="{ name: 'chat', params: { id: c.id } }"
              class="used-link"
              :title="c.title"
            >{{ c.title }}</RouterLink>
            <span v-if="p.conversations.length > 2" class="used-more">+{{ p.conversations.length - 2 }} more</span>
          </div>
        </li>
      </ul>
      <div v-else class="no-match">
        <p>No papers match “{{ query }}”{{ filter !== 'all' ? ' with this filter' : '' }}.</p>
        <button type="button" class="btn btn-ghost btn-sm" @click="(query = ''), (filter = 'all')">Clear search</button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.page { max-width: 1040px; margin: 0 auto; padding: 32px clamp(16px, 4vw, 64px) 64px; display: flex; flex-direction: column; gap: 24px; }
.page-head { display: flex; flex-direction: column; gap: 8px; }
.page-head h1 { font-size: clamp(28px, 3vw, 38px); font-weight: 900; letter-spacing: -0.02em; }
.page-head p { max-width: 640px; color: var(--secondary); }

.empty {
  display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 56px 24px; text-align: center;
  border: 2px dashed var(--line-strong); border-radius: var(--r-lg); background: var(--surface);
}
.empty-icon { width: 56px; height: 56px; border-radius: var(--r-lg); display: flex; align-items: center; justify-content: center; background: var(--tint); color: var(--accent-text); }
.empty h2 { font-size: 20px; font-weight: 900; }
.empty p { max-width: 420px; color: var(--secondary); margin-bottom: 4px; }

.toolbar { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; }
.search { position: relative; flex: 1 1 280px; max-width: 420px; }
.search .input { height: 44px; padding-left: 40px; }
.search-icon { position: absolute; left: 14px; top: 14px; color: var(--dim); }
.filters { display: flex; flex-wrap: wrap; gap: 6px; }
.filter {
  min-height: 36px; padding: 0 14px; border-radius: var(--pill); cursor: pointer;
  border: 1px solid var(--line-strong); background: transparent; color: var(--dim); font-size: 13px; font-weight: 700;
}
.filter.is-on { border-color: var(--accent); background: var(--accent-soft); color: var(--accent-text); }

.count { font-size: 14px; color: var(--dim); }

.list { list-style: none; margin: 0; padding: 0; border: 1px solid var(--line); border-radius: 12px; background: var(--surface); overflow: hidden; }
.paper {
  display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px 16px; align-items: center;
  padding: 16px 20px; border-bottom: 1px solid var(--line);
}
.paper:last-child { border-bottom: 0; }
.paper:hover { background: var(--note); }
.paper-main { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.paper-title { display: inline-flex; align-items: center; gap: 6px; font-size: 15px; font-weight: 700; color: var(--text); }
.paper-meta { font-size: 13px; color: var(--dim); }
.paper-tags { justify-self: end; }
.paper-used { grid-column: 1 / -1; display: flex; flex-wrap: wrap; align-items: center; gap: 6px 10px; font-size: 13px; }
.used-label { color: var(--dim); }
.used-link { max-width: 320px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.used-more { color: var(--dim); }

.no-match { display: flex; flex-direction: column; align-items: flex-start; gap: 10px; color: var(--secondary); }
</style>
