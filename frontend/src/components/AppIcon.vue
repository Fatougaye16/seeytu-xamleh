<script setup lang="ts">
import { computed, type PropType } from 'vue'
import { iconShapes, type IconName } from '@/lib/icons'

/** Decorative by default; pass `label` when the icon is the only thing conveying meaning. */
const props = defineProps({
  name: { type: String as PropType<IconName>, required: true },
  size: { type: Number, default: 18 },
  strokeWidth: { type: Number, default: 1.8 },
  label: { type: String, default: undefined },
})

const shapes = computed(() => iconShapes(props.name))
</script>

<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    :stroke-width="strokeWidth"
    stroke-linecap="round"
    stroke-linejoin="round"
    :role="label ? 'img' : undefined"
    :aria-label="label"
    :aria-hidden="label ? undefined : 'true'"
    focusable="false"
    class="app-icon"
  >
    <template v-for="(s, i) in shapes" :key="i">
      <path v-if="s.kind === 'path'" :d="s.d" />
      <circle v-else-if="s.kind === 'circle'" :cx="s.cx" :cy="s.cy" :r="s.r" />
      <rect v-else :x="s.x" :y="s.y" :width="s.w" :height="s.h" :rx="s.rx" />
    </template>
  </svg>
</template>

<style scoped>
.app-icon { flex: none; }
</style>
