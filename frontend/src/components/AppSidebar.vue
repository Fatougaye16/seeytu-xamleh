<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import AppIcon from './AppIcon.vue'
import { useAuthStore } from '@/stores/auth'
import { useChatsStore } from '@/stores/chats'

const emit = defineEmits<{ navigate: [] }>()

const auth = useAuthStore()
const chats = useChatsStore()
const route = useRoute()
const router = useRouter()

function signOut() {
  auth.logout()
  emit('navigate')
  router.push({ name: 'signin' })
}
</script>

<template>
  <nav class="sidebar" aria-label="Main">
    <RouterLink :to="{ name: 'home' }" class="brand" @click="emit('navigate')">
      <span class="brand-name">Seeytu-Xamleh</span>
      <span class="eyebrow brand-tag">Explore. Learn. Publish.</span>
    </RouterLink>

    <RouterLink :to="{ name: 'home' }" class="btn btn-primary new-chat" @click="emit('navigate')">
      <AppIcon name="plus" :size="16" :stroke-width="2.4" />
      New chat
    </RouterLink>

    <div class="nav-group">
      <RouterLink
        :to="{ name: 'home' }"
        class="nav-item"
        :class="{ 'is-active': route.name === 'home' || route.name === 'chat' }"
        @click="emit('navigate')"
      >
        <AppIcon name="chat" />
        <span class="nav-label">Chats</span>
      </RouterLink>
      <RouterLink :to="{ name: 'paths' }" class="nav-item" active-class="is-active" @click="emit('navigate')">
        <AppIcon name="path" />
        <span class="nav-label">Learning paths</span>
      </RouterLink>
      <RouterLink :to="{ name: 'library' }" class="nav-item" active-class="is-active" @click="emit('navigate')">
        <AppIcon name="library" />
        <span class="nav-label">Library</span>
        <span class="nav-count">{{ chats.library.length }}</span>
      </RouterLink>
    </div>

    <div class="recent">
      <h2 class="eyebrow recent-heading">Recent</h2>
      <p v-if="!chats.sorted.length" class="recent-empty">Your questions will show up here.</p>
      <ul v-else class="recent-list">
        <li v-for="c in chats.sorted.slice(0, 30)" :key="c.id">
          <RouterLink
            :to="{ name: 'chat', params: { id: c.id } }"
            class="recent-item"
            active-class="is-active"
            :title="c.title"
            @click="emit('navigate')"
          >
            <span v-if="chats.isBusy(c.id)" class="pulse-dot busy-dot" aria-hidden="true"></span>
            <span class="recent-title">{{ c.title }}</span>
            <span v-if="chats.isBusy(c.id)" class="visually-hidden">(answering)</span>
          </RouterLink>
        </li>
      </ul>
    </div>

    <div class="account">
      <span class="avatar" aria-hidden="true">{{ auth.initials }}</span>
      <span class="account-text">
        <span class="account-name">{{ auth.displayName }}</span>
        <span class="account-handle">@{{ auth.username }}</span>
      </span>
      <button class="btn btn-icon account-out" type="button" aria-label="Sign out" title="Sign out" @click="signOut">
        <AppIcon name="logout" />
      </button>
    </div>
  </nav>
</template>

<style scoped>
.sidebar {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 24px 16px;
  background: var(--surface);
  border-right: 1px solid var(--line);
  overflow-y: auto;
}
.brand { display: flex; flex-direction: column; gap: 4px; padding: 0 8px; text-decoration: none !important; }
.brand-name { font-size: 18px; font-weight: 900; color: var(--text); }
.brand-tag { font-size: 11px; }
.new-chat { width: 100%; }

.nav-group { display: flex; flex-direction: column; gap: 2px; }
.nav-item {
  display: flex; align-items: center; gap: 12px;
  min-height: 44px; padding: 0 12px; border-radius: var(--r);
  color: var(--secondary); font-size: 15px; text-decoration: none !important;
  transition: background var(--t), color var(--t);
}
.nav-item:hover { background: var(--tint); color: var(--text); }
.nav-item.is-active { background: var(--tint); color: var(--text); font-weight: 700; }
.nav-label { flex: 1; }
.nav-count { font-family: var(--mono); font-size: 12px; color: var(--dim); }

.recent { display: flex; flex-direction: column; gap: 6px; flex: 1; min-height: 0; }
.recent-heading { padding: 0 12px; font-size: 11px; font-weight: 400; }
.recent-empty { padding: 0 12px; font-size: 14px; color: var(--dim); }
.recent-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 2px; }
.recent-item {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 12px; border-radius: var(--r);
  color: var(--secondary); font-size: 14px; text-decoration: none !important;
}
.recent-item:hover { background: var(--tint); color: var(--text); }
.recent-item.is-active { background: var(--tint); color: var(--text); font-weight: 700; }
.recent-title { min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.busy-dot { width: 8px; height: 8px; flex: none; }

.account { display: flex; align-items: center; gap: 12px; padding: 16px 8px 0; border-top: 1px solid var(--line); }
.avatar {
  width: 36px; height: 36px; flex: none; border-radius: var(--pill);
  display: flex; align-items: center; justify-content: center;
  background: var(--tint-strong); color: var(--text); font-size: 13px; font-weight: 700;
}
.account-text { flex: 1; min-width: 0; display: flex; flex-direction: column; line-height: 1.35; }
.account-name { font-size: 14px; font-weight: 700; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.account-handle { font-size: 13px; color: var(--dim); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.account-out { background: transparent; color: var(--dim); }
.account-out:hover { background: var(--tint); color: var(--text); }
</style>
