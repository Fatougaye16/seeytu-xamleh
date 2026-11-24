import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import { ask as askApi, type Source } from '@/api/rag'
import { ApiError } from '@/api/client'
import { readJson, writeJson } from '@/lib/storage'
import { useAuthStore } from './auth'

export interface UserMessage {
  id: string
  role: 'user'
  text: string
  at: number
}

export interface AssistantMessage {
  id: string
  role: 'assistant'
  status: 'pending' | 'done' | 'error' | 'stopped'
  question: string
  answer?: string
  sources?: Source[]
  error?: string
  startedAt: number
  durationMs?: number
}

export type Message = UserMessage | AssistantMessage

export interface Conversation {
  id: string
  title: string
  createdAt: number
  updatedAt: number
  messages: Message[]
}

export interface LibraryPaper {
  source: Source
  conversations: { id: string; title: string }[]
  lastUsed: number
}

const uid = () => crypto.randomUUID()
const titleFrom = (q: string) => (q.length > 80 ? `${q.slice(0, 77).trimEnd()}…` : q)

/**
 * Conversations live in this browser's localStorage, one list per signed-in user,
 * because the backend has no conversation endpoints yet.
 */
export const useChatsStore = defineStore('chats', () => {
  const auth = useAuthStore()
  const conversations = ref<Conversation[]>([])
  const controllers = new Map<string, AbortController>() // not reactive on purpose
  const busyIds = ref(new Set<string>()) // reactive mirror of controllers' keys, for the UI

  const storageKey = computed(() => (auth.username ? `sx:chats:${auth.username}` : null))

  function load() {
    const key = storageKey.value
    const saved = key ? readJson<Conversation[]>(key, []) : []
    // A request can't survive a reload: mark anything left pending as interrupted.
    for (const c of saved) {
      for (const m of c.messages) {
        if (m.role === 'assistant' && m.status === 'pending') {
          m.status = 'error'
          m.error = 'This answer was interrupted when the page reloaded.'
        }
      }
    }
    conversations.value = saved
  }

  watch(storageKey, load, { immediate: true })
  watch(
    conversations,
    (value) => {
      if (storageKey.value) writeJson(storageKey.value, value)
    },
    { deep: true },
  )

  const sorted = computed(() => [...conversations.value].sort((a, b) => b.updatedAt - a.updatedAt))

  const library = computed<LibraryPaper[]>(() => {
    const byId = new Map<string, LibraryPaper>()
    for (const conv of conversations.value) {
      for (const m of conv.messages) {
        if (m.role !== 'assistant' || !m.sources) continue
        for (const s of m.sources) {
          const entry = byId.get(s.document_id) ?? { source: s, conversations: [], lastUsed: 0 }
          entry.source = { ...entry.source, ...s }
          if (!entry.conversations.some((c) => c.id === conv.id)) {
            entry.conversations.push({ id: conv.id, title: conv.title })
          }
          entry.lastUsed = Math.max(entry.lastUsed, m.startedAt)
          byId.set(s.document_id, entry)
        }
      }
    }
    return [...byId.values()].sort((a, b) => b.lastUsed - a.lastUsed)
  })

  const get = (id: string) => conversations.value.find((c) => c.id === id)

  function isBusy(id: string) {
    return busyIds.value.has(id)
  }

  async function runAsk(conv: Conversation, question: string) {
    const pending: AssistantMessage = {
      id: uid(),
      role: 'assistant',
      status: 'pending',
      question,
      startedAt: Date.now(),
    }
    conv.messages.push({ id: uid(), role: 'user', text: question, at: Date.now() }, pending)
    conv.updatedAt = Date.now()
    // Work on the reactive copy so updates re-render.
    const msg = conv.messages[conv.messages.length - 1] as AssistantMessage

    const controller = new AbortController()
    controllers.set(conv.id, controller)
    busyIds.value.add(conv.id)
    try {
      const res = await askApi(question, controller.signal)
      msg.answer = res.answer
      msg.sources = res.sources
      msg.status = 'done'
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        msg.status = 'stopped'
      } else {
        msg.status = 'error'
        msg.error = err instanceof ApiError ? err.message : 'Something went wrong while answering.'
      }
    } finally {
      msg.durationMs = Date.now() - msg.startedAt
      conv.updatedAt = Date.now()
      controllers.delete(conv.id)
      busyIds.value.delete(conv.id)
    }
  }

  /** Start a new conversation; resolves with its id as soon as it exists (the answer keeps loading). */
  function start(question: string): string {
    const conv: Conversation = {
      id: uid(),
      title: titleFrom(question),
      createdAt: Date.now(),
      updatedAt: Date.now(),
      messages: [],
    }
    conversations.value.push(conv)
    void runAsk(get(conv.id)!, question)
    return conv.id
  }

  function followUp(id: string, question: string) {
    const conv = get(id)
    if (conv && !isBusy(id)) void runAsk(conv, question)
  }

  function retry(id: string, messageId: string) {
    const conv = get(id)
    if (!conv || isBusy(id)) return
    const idx = conv.messages.findIndex((m) => m.id === messageId)
    const failed = conv.messages[idx]
    if (!failed || failed.role !== 'assistant') return
    conv.messages.splice(idx - 1, 2) // drop the question + failed answer, then ask again
    void runAsk(conv, failed.question)
  }

  function stop(id: string) {
    controllers.get(id)?.abort()
  }

  function remove(id: string) {
    stop(id)
    conversations.value = conversations.value.filter((c) => c.id !== id)
  }

  return { conversations, sorted, library, get, isBusy, start, followUp, retry, stop, remove }
})
