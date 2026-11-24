<script setup lang="ts">
import { computed } from 'vue'
import { parseAnswer, type Segment } from '@/lib/answer'

const props = defineProps<{
  answer: string
  /** Citation numbers that have a matching source; others render as plain text. */
  validCitations: number[]
  activeCitation: number | null
}>()
const emit = defineEmits<{ cite: [n: number] }>()

const blocks = computed(() => parseAnswer(props.answer))
const valid = computed(() => new Set(props.validCitations))

const isCite = (s: Segment): s is Extract<Segment, { kind: 'cite' }> => s.kind === 'cite'
</script>

<template>
  <div class="answer">
    <template v-for="(block, bi) in blocks" :key="bi">
      <h3 v-if="block.type === 'heading'" class="answer-heading">
        <template v-for="(seg, si) in block.segments" :key="si">{{ isCite(seg) ? `[${seg.n}]` : seg.text }}</template>
      </h3>

      <p v-else-if="block.type === 'paragraph'">
        <template v-for="(seg, si) in block.segments" :key="si">
          <strong v-if="seg.kind === 'bold'">{{ seg.text }}</strong>
          <code v-else-if="seg.kind === 'code'">{{ seg.text }}</code>
          <button
            v-else-if="isCite(seg) && valid.has(seg.n)"
            type="button"
            class="cite"
            :class="{ 'is-active': activeCitation === seg.n }"
            :aria-label="`Show source ${seg.n}`"
            :aria-pressed="activeCitation === seg.n"
            @click="emit('cite', seg.n)"
          >{{ seg.n }}</button>
          <template v-else-if="isCite(seg)">[{{ seg.n }}]</template>
          <template v-else>{{ seg.text }}</template>
        </template>
      </p>

      <component :is="block.ordered ? 'ol' : 'ul'" v-else-if="block.type === 'list'" class="answer-list">
        <li v-for="(item, ii) in block.items" :key="ii">
          <template v-for="(seg, si) in item" :key="si">
            <strong v-if="seg.kind === 'bold'">{{ seg.text }}</strong>
            <code v-else-if="seg.kind === 'code'">{{ seg.text }}</code>
            <button
              v-else-if="isCite(seg) && valid.has(seg.n)"
              type="button"
              class="cite"
              :class="{ 'is-active': activeCitation === seg.n }"
              :aria-label="`Show source ${seg.n}`"
              :aria-pressed="activeCitation === seg.n"
              @click="emit('cite', seg.n)"
            >{{ seg.n }}</button>
            <template v-else-if="isCite(seg)">[{{ seg.n }}]</template>
            <template v-else>{{ seg.text }}</template>
          </template>
        </li>
      </component>
    </template>
  </div>
</template>

<style scoped>
.answer { display: flex; flex-direction: column; gap: 14px; font-size: 16px; line-height: 1.7; color: var(--body); }
.answer strong { color: var(--text); }
.answer code { font-family: var(--mono); font-size: 0.9em; background: var(--tint); padding: 1px 5px; border-radius: 4px; }
.answer-heading { font-size: 17px; font-weight: 900; margin-top: 6px; }
.answer-list { margin: 0; padding-left: 22px; display: flex; flex-direction: column; gap: 8px; }

.cite {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 24px; height: 22px; padding: 0 6px; margin: 0 1px;
  border: 0; border-radius: var(--r-sm);
  background: var(--accent-soft); color: var(--accent-text);
  font-family: var(--mono); font-size: 12px; font-weight: 500;
  vertical-align: 1px; cursor: pointer;
  transition: background var(--t), color var(--t);
}
.cite:hover { background: var(--accent-soft-strong); }
.cite.is-active { background: var(--accent); color: var(--on-accent); }
</style>
