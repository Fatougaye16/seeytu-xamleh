import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as authApi from '@/api/auth'
import { readJson, removeKey, writeJson } from '@/lib/storage'

const STORAGE_KEY = 'sx:auth'

interface SavedSession {
  token: string
  username: string
  displayName: string
}

/** Reads `exp` from a JWT without verifying it (the server verifies; this only avoids using a dead token). */
function tokenExpiry(token: string): number | null {
  try {
    const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')))
    return typeof payload.exp === 'number' ? payload.exp * 1000 : null
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  const saved = readJson<SavedSession | null>(STORAGE_KEY, null)
  const token = ref<string | null>(saved?.token ?? null)
  const username = ref<string | null>(saved?.username ?? null)
  const displayName = ref<string | null>(saved?.displayName ?? null)

  const initials = computed(() => {
    const parts = (displayName.value ?? username.value ?? '?').trim().split(/\s+/)
    return parts.slice(0, 2).map((p) => p[0]?.toUpperCase() ?? '').join('') || '?'
  })

  function isSessionValid(): boolean {
    if (!token.value) return false
    const exp = tokenExpiry(token.value)
    return exp === null || exp > Date.now()
  }

  function persist() {
    if (token.value && username.value) {
      writeJson(STORAGE_KEY, { token: token.value, username: username.value, displayName: displayName.value ?? username.value })
    } else {
      removeKey(STORAGE_KEY)
    }
  }

  async function login(user: string, password: string, name?: string) {
    token.value = await authApi.login(user, password)
    username.value = user
    displayName.value = name ?? readJson<Record<string, string>>('sx:names', {})[user] ?? user
    persist()
  }

  async function register(input: authApi.RegisterInput) {
    await authApi.register(input)
    const name = `${input.firstName} ${input.lastName}`.trim()
    // Login only returns a token, so remember the display name locally for next time.
    writeJson('sx:names', { ...readJson<Record<string, string>>('sx:names', {}), [input.username]: name })
    await login(input.username, input.password, name)
  }

  function logout() {
    token.value = null
    username.value = null
    displayName.value = null
    persist()
  }

  return { token, username, displayName, initials, isSessionValid, login, register, logout }
})
