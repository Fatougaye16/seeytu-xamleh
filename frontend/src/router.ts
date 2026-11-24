import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AppShell from '@/layouts/AppShell.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/signin',
      name: 'signin',
      component: () => import('@/views/SignInView.vue'),
      meta: { public: true, title: 'Sign in' },
    },
    {
      path: '/',
      component: AppShell,
      children: [
        { path: '', name: 'home', component: () => import('@/views/HomeView.vue'), meta: { title: 'New chat' } },
        { path: 'chat/:id', name: 'chat', component: () => import('@/views/ConversationView.vue'), meta: { title: 'Chat' } },
        { path: 'library', name: 'library', component: () => import('@/views/LibraryView.vue'), meta: { title: 'Library' } },
        { path: 'paths', name: 'paths', component: () => import('@/views/LearningPathsView.vue'), meta: { title: 'Learning paths' } },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  const signedIn = auth.isSessionValid()
  if (!signedIn && auth.token) auth.logout() // expired token

  if (!to.meta.public && !signedIn) {
    return { name: 'signin', query: to.fullPath !== '/' ? { redirect: to.fullPath } : {} }
  }
  if (to.name === 'signin' && signedIn) return { name: 'home' }
})

router.afterEach((to) => {
  const title = to.meta.title as string | undefined
  document.title = title ? `${title} · Seeytu-Xamleh` : 'Seeytu-Xamleh'
})

export default router
