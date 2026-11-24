<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppSidebar from '@/components/AppSidebar.vue'
import AppIcon from '@/components/AppIcon.vue'

const route = useRoute()
const drawerOpen = ref(false)
const menuButton = ref<HTMLButtonElement | null>(null)
const drawer = ref<HTMLElement | null>(null)

function open() {
  drawerOpen.value = true
  nextTick(() => drawer.value?.querySelector<HTMLElement>('a, button')?.focus())
}
function close(returnFocus = true) {
  if (!drawerOpen.value) return
  drawerOpen.value = false
  if (returnFocus) nextTick(() => menuButton.value?.focus())
}
function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') close()
}

watch(() => route.fullPath, () => close(false))
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <a href="#main" class="skip-link">Skip to content</a>
  <div class="shell">
    <header class="topbar">
      <button
        ref="menuButton"
        type="button"
        class="btn btn-icon topbar-menu"
        aria-label="Open menu"
        :aria-expanded="drawerOpen"
        aria-controls="app-sidebar"
        @click="open"
      >
        <AppIcon name="menu" :size="20" />
      </button>
      <RouterLink :to="{ name: 'home' }" class="topbar-brand">Seeytu-Xamleh</RouterLink>
      <RouterLink :to="{ name: 'home' }" class="btn btn-icon topbar-new" aria-label="New chat">
        <AppIcon name="plus" :size="20" :stroke-width="2.2" />
      </RouterLink>
    </header>

    <div v-if="drawerOpen" class="backdrop" aria-hidden="true" @click="close()"></div>

    <aside
      id="app-sidebar"
      ref="drawer"
      class="sidebar-slot"
      :class="{ 'is-open': drawerOpen }"
    >
      <button type="button" class="btn btn-icon drawer-close" aria-label="Close menu" @click="close()">
        <AppIcon name="close" :size="20" />
      </button>
      <AppSidebar @navigate="close(false)" />
    </aside>

    <main id="main" class="main" tabindex="-1">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.skip-link {
  position: absolute; left: 12px; top: -100px; z-index: 100;
  padding: 10px 16px; border-radius: var(--r); background: var(--accent); color: var(--on-accent); font-weight: 700;
}
.skip-link:focus { top: 12px; }

.shell { min-height: 100vh; display: grid; grid-template-columns: var(--sidebar-w) minmax(0, 1fr); }
.sidebar-slot { position: sticky; top: 0; height: 100vh; }
.main { min-width: 0; outline: none; }

.topbar, .drawer-close, .backdrop { display: none; }

@media (max-width: 899px) {
  .shell { grid-template-columns: minmax(0, 1fr); grid-template-rows: auto 1fr; }
  .topbar {
    position: sticky; top: 0; z-index: 20;
    display: flex; align-items: center; gap: 8px;
    height: 60px; padding: 0 8px;
    background: var(--surface); border-bottom: 1px solid var(--line);
  }
  .topbar-menu, .topbar-new { background: transparent; color: var(--text); }
  .topbar-brand { flex: 1; font-weight: 900; color: var(--text); text-decoration: none !important; }

  .sidebar-slot {
    position: fixed; inset: 0 auto 0 0; z-index: 40;
    width: min(320px, 86vw); height: 100%;
    transform: translateX(-100%); visibility: hidden;
    transition: transform var(--t), visibility 0s linear 200ms;
    box-shadow: var(--shadow-2);
  }
  .sidebar-slot.is-open { transform: none; visibility: visible; transition: transform var(--t); }
  .drawer-close { display: inline-flex; position: absolute; top: 14px; right: 10px; z-index: 1; background: transparent; color: var(--dim); }
  .backdrop { display: block; position: fixed; inset: 0; z-index: 30; background: rgba(18, 55, 42, 0.35); }
}
</style>
