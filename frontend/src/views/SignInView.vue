<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppIcon from '@/components/AppIcon.vue'
import { useAuthStore } from '@/stores/auth'
import { ApiError } from '@/api/client'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

type Mode = 'signin' | 'register'
const mode = ref<Mode>('signin')
const busy = ref(false)
const formError = ref('')

const form = reactive({ firstName: '', lastName: '', email: '', username: '', password: '' })
const touched = reactive<Record<keyof typeof form, boolean>>({
  firstName: false, lastName: false, email: false, username: false, password: false,
})

const isRegister = computed(() => mode.value === 'register')

const errors = computed(() => {
  const e: Partial<Record<keyof typeof form, string>> = {}
  if (!form.username.trim()) e.username = 'Enter your username.'
  else if (isRegister.value && !/^[a-zA-Z0-9_.-]{3,30}$/.test(form.username.trim()))
    e.username = 'Use 3–30 letters, numbers, dots, dashes or underscores.'
  if (!form.password) e.password = 'Enter your password.'
  else if (isRegister.value && form.password.length < 8) e.password = 'Use at least 8 characters.'
  if (isRegister.value) {
    if (!form.firstName.trim()) e.firstName = 'Enter your first name.'
    if (!form.lastName.trim()) e.lastName = 'Enter your last name.'
    if (!form.email.trim()) e.email = 'Enter your email.'
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) e.email = 'That email doesn’t look right.'
  }
  return e
})

const show = (field: keyof typeof form) => (touched[field] ? errors.value[field] : undefined)

function switchMode(next: Mode) {
  mode.value = next
  formError.value = ''
  for (const k of Object.keys(touched) as (keyof typeof form)[]) touched[k] = false
}

async function submit() {
  for (const k of Object.keys(touched) as (keyof typeof form)[]) touched[k] = true
  formError.value = ''
  if (Object.keys(errors.value).length) {
    const first = Object.keys(errors.value)[0]
    document.getElementById(`f-${first}`)?.focus()
    return
  }
  busy.value = true
  try {
    if (isRegister.value) {
      await auth.register({
        firstName: form.firstName.trim(),
        lastName: form.lastName.trim(),
        email: form.email.trim(),
        username: form.username.trim(),
        password: form.password,
      })
    } else {
      await auth.login(form.username.trim(), form.password)
    }
    const redirect = typeof route.query.redirect === 'string' && route.query.redirect.startsWith('/') ? route.query.redirect : '/'
    router.replace(redirect)
  } catch (err) {
    formError.value = err instanceof ApiError ? err.message : 'Something went wrong. Please try again.'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="signin">
    <section class="hero">
      <div class="hero-brand">
        <span class="hero-name">Seeytu-Xamleh</span>
        <span class="eyebrow">Explore. Learn. Publish.</span>
      </div>

      <div class="hero-body">
        <h1 class="hero-title">Ask research a question. Get an answer you can check.</h1>
        <p class="hero-lede">
          Every answer is built from real papers on arXiv and OpenAlex, and every claim links back to the passage it came from.
        </p>
        <figure class="example" aria-label="Example of a cited answer">
          <p>
            FLARE decides <em>when</em> to retrieve: it drafts the next sentence and only searches again if the draft
            contains low-confidence words <span class="example-cite">1</span>
          </p>
          <figcaption>
            <span class="example-ref">[1]</span>
            Active Retrieval Augmented Generation · Jiang et al. · EMNLP 2023
          </figcaption>
        </figure>
      </div>

      <p class="hero-foot"><em>Seeytu-Xamleh</em> is Wolof for “explore and teach.”</p>
    </section>

    <section class="panel">
      <div class="panel-inner">
        <div class="mobile-brand">
          <span class="hero-name">Seeytu-Xamleh</span>
          <span class="eyebrow">Explore. Learn. Publish.</span>
        </div>
        <div class="panel-head">
          <h2>{{ isRegister ? 'Create your account' : 'Welcome back' }}</h2>
          <p>{{ isRegister ? 'Your chats and papers will be saved to it.' : 'Pick up where your last question left off.' }}</p>
        </div>

        <div class="segmented" role="group" aria-label="Choose sign in or create account">
          <button type="button" :aria-pressed="!isRegister" :class="{ 'is-on': !isRegister }" @click="switchMode('signin')">Sign in</button>
          <button type="button" :aria-pressed="isRegister" :class="{ 'is-on': isRegister }" @click="switchMode('register')">Create account</button>
        </div>

        <form class="form" novalidate @submit.prevent="submit">
          <p v-if="formError" class="alert alert-error" role="alert">
            <AppIcon name="alert" />
            <span>{{ formError }}</span>
          </p>

          <template v-if="isRegister">
            <div class="row-2">
              <div class="field">
                <label class="field-label" for="f-firstName">First name</label>
                <input id="f-firstName" v-model="form.firstName" class="input" autocomplete="given-name"
                  :aria-invalid="!!show('firstName')" :aria-describedby="show('firstName') ? 'e-firstName' : undefined"
                  @blur="touched.firstName = true" />
                <p v-if="show('firstName')" id="e-firstName" class="field-error">{{ show('firstName') }}</p>
              </div>
              <div class="field">
                <label class="field-label" for="f-lastName">Last name</label>
                <input id="f-lastName" v-model="form.lastName" class="input" autocomplete="family-name"
                  :aria-invalid="!!show('lastName')" :aria-describedby="show('lastName') ? 'e-lastName' : undefined"
                  @blur="touched.lastName = true" />
                <p v-if="show('lastName')" id="e-lastName" class="field-error">{{ show('lastName') }}</p>
              </div>
            </div>
            <div class="field">
              <label class="field-label" for="f-email">Email</label>
              <input id="f-email" v-model="form.email" class="input" type="email" autocomplete="email" placeholder="you@example.com"
                :aria-invalid="!!show('email')" :aria-describedby="show('email') ? 'e-email' : undefined"
                @blur="touched.email = true" />
              <p v-if="show('email')" id="e-email" class="field-error">{{ show('email') }}</p>
            </div>
          </template>

          <div class="field">
            <label class="field-label" for="f-username">Username</label>
            <input id="f-username" v-model="form.username" class="input" autocomplete="username" autocapitalize="none" spellcheck="false"
              :aria-invalid="!!show('username')" :aria-describedby="show('username') ? 'e-username' : undefined"
              @blur="touched.username = true" />
            <p v-if="show('username')" id="e-username" class="field-error">{{ show('username') }}</p>
          </div>

          <div class="field">
            <label class="field-label" for="f-password">Password</label>
            <input id="f-password" v-model="form.password" class="input" type="password"
              :autocomplete="isRegister ? 'new-password' : 'current-password'"
              :aria-invalid="!!show('password')"
              :aria-describedby="show('password') ? 'e-password' : isRegister ? 'h-password' : undefined"
              @blur="touched.password = true" />
            <p v-if="show('password')" id="e-password" class="field-error">{{ show('password') }}</p>
            <p v-else-if="isRegister" id="h-password" class="field-hint">At least 8 characters.</p>
          </div>

          <button class="btn btn-primary submit" type="submit" :disabled="busy">
            <span v-if="busy" class="spinner" aria-hidden="true"></span>
            {{ busy ? (isRegister ? 'Creating account…' : 'Signing in…') : isRegister ? 'Create account' : 'Sign in' }}
            <AppIcon v-if="!busy" name="arrowRight" :size="16" :stroke-width="2.4" />
          </button>
        </form>

        <p class="panel-foot">Answers are generated by a model running on this computer.</p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.signin { min-height: 100vh; display: flex; flex-wrap: wrap; }

.hero {
  flex: 1 1 520px; min-width: 0;
  display: flex; flex-direction: column; justify-content: space-between; gap: 48px;
  padding: clamp(32px, 6vw, 88px);
  background: var(--surface); border-right: 1px solid var(--line);
}
.hero-brand { display: flex; flex-direction: column; gap: 6px; }
.hero-name { font-size: 20px; font-weight: 900; color: var(--text); }
.hero-body { display: flex; flex-direction: column; gap: 28px; max-width: 520px; }
.hero-title { font-size: clamp(32px, 3.6vw, 46px); line-height: 1.12; font-weight: 900; letter-spacing: -0.02em; text-wrap: balance; }
.hero-lede { font-size: 18px; color: var(--secondary); }
.hero-foot { font-size: 14px; color: var(--dim); }

.example { margin: 0; padding: 20px; display: flex; flex-direction: column; gap: 14px; background: var(--tint); border: 1px solid var(--line-strong); border-radius: 12px; }
.example p { font-size: 15px; line-height: 1.65; color: var(--body); }
.example-cite {
  display: inline-flex; align-items: center; justify-content: center; min-width: 22px; height: 20px; padding: 0 6px;
  border-radius: var(--r-sm); background: var(--accent-soft); color: var(--accent-text);
  font-family: var(--mono); font-size: 12px; vertical-align: 1px;
}
.example figcaption { display: flex; gap: 10px; padding-top: 12px; border-top: 1px solid var(--line-strong); font-size: 13px; color: var(--dim); }
.example-ref { font-family: var(--mono); color: var(--accent-text); }

.panel { flex: 1 1 420px; min-width: 0; display: flex; align-items: center; justify-content: center; padding: clamp(32px, 6vw, 88px) 24px; }
.panel-inner { width: 100%; max-width: 400px; display: flex; flex-direction: column; gap: 28px; }
.panel-head { display: flex; flex-direction: column; gap: 8px; }
.panel-head h2 { font-size: 30px; font-weight: 900; }
.panel-head p { font-size: 15px; color: var(--dim); }

.segmented { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 4px; padding: 4px; background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-md); }
.segmented button { height: 40px; border: 0; border-radius: 7px; background: transparent; color: var(--dim); font-size: 15px; font-weight: 700; cursor: pointer; }
.segmented button.is-on { background: var(--tint-strong); color: var(--text); box-shadow: var(--shadow-1); }

.form { display: flex; flex-direction: column; gap: 18px; }
.row-2 { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.submit { height: 52px; margin-top: 6px; font-size: 16px; }
.panel-foot { font-size: 13px; color: var(--dim); }

.spinner { width: 16px; height: 16px; border-radius: 50%; border: 2px solid rgba(255, 255, 255, 0.4); border-top-color: #fff; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.mobile-brand { display: none; }

@media (max-width: 899px) {
  .hero { display: none; }
  .mobile-brand { display: flex; flex-direction: column; gap: 4px; }
}
</style>
