<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import AppIcon from './AppIcon.vue'

const props = withDefaults(
  defineProps<{
    label: string
    placeholder?: string
    size?: 'large' | 'compact'
    disabled?: boolean
    disabledHint?: string
    autofocus?: boolean
  }>(),
  { placeholder: '', size: 'compact', disabled: false, disabledHint: '', autofocus: false },
)
const emit = defineEmits<{ submit: [text: string] }>()

const text = ref('')
const textarea = ref<HTMLTextAreaElement | null>(null)
const inputId = `composer-${Math.random().toString(36).slice(2, 8)}`

function autosize() {
  const el = textarea.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 240)}px`
}
watch(text, () => nextTick(autosize))

function submit() {
  const value = text.value.trim()
  if (!value || props.disabled) return
  emit('submit', value)
  text.value = ''
}

// Enter sends, Shift+Enter adds a line; ignore Enter while an IME is composing.
function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    submit()
  }
}

defineExpose({ focus: () => textarea.value?.focus(), setText: (v: string) => (text.value = v) })
</script>

<template>
  <form class="composer" :class="`is-${size}`" @submit.prevent="submit">
    <label :for="inputId" class="visually-hidden">{{ label }}</label>
    <textarea
      :id="inputId"
      ref="textarea"
      v-model="text"
      :rows="size === 'large' ? 3 : 1"
      :placeholder="placeholder"
      :autofocus="autofocus"
      :aria-describedby="disabled && disabledHint ? `${inputId}-hint` : undefined"
      @keydown="onKeydown"
    ></textarea>
    <div class="composer-actions">
      <span v-if="disabled && disabledHint" :id="`${inputId}-hint`" class="composer-hint">{{ disabledHint }}</span>
      <span v-else-if="size === 'large'" class="composer-hint">Enter to ask · Shift+Enter for a new line</span>
      <button
        v-if="size === 'large'"
        class="btn btn-primary"
        type="submit"
        :disabled="disabled || !text.trim()"
      >
        Ask
        <AppIcon name="arrowRight" :size="16" :stroke-width="2.4" />
      </button>
      <button
        v-else
        class="btn btn-primary btn-icon"
        type="submit"
        aria-label="Send"
        :disabled="disabled || !text.trim()"
      >
        <AppIcon name="send" :stroke-width="2.4" />
      </button>
    </div>
  </form>
</template>

<style scoped>
.composer {
  display: flex;
  background: var(--surface);
  border: 1px solid var(--input-border);
  border-radius: var(--r-lg);
  transition: border-color var(--t), box-shadow var(--t);
}
.composer:focus-within { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }

.composer.is-large { flex-direction: column; gap: 12px; padding: 16px; box-shadow: var(--shadow-2); border-radius: 16px; }
.composer.is-compact { align-items: flex-end; gap: 12px; padding: 8px 8px 8px 16px; }

textarea {
  flex: 1;
  resize: none;
  background: transparent;
  border: 0;
  outline: none;
  color: var(--text);
  font: inherit;
  line-height: 1.55;
}
.is-large textarea { font-size: 17px; padding: 4px 4px 0; min-height: 84px; }
.is-compact textarea { font-size: 16px; padding: 10px 0; }
textarea::placeholder { color: var(--dim); opacity: 0.85; }

.composer-actions { display: flex; align-items: center; justify-content: flex-end; gap: 12px; }
.is-large .composer-actions { justify-content: space-between; flex-wrap: wrap; }
.composer-hint { font-size: 13px; color: var(--dim); }
.is-compact .composer-hint { display: none; }
</style>
