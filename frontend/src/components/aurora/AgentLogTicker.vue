<template>
  <div ref="root" class="agent-log-ticker" aria-live="polite" aria-atomic="false">
    <div class="ticker-header">
      <span class="ticker-title">Agent decision feed</span>
    </div>
    <ul class="ticker-list" :class="{ empty: visibleEntries.length === 0 }">
      <li
        v-for="(entry, i) in visibleEntries"
        :key="entry.timestamp + entry.post_text"
        class="ticker-row"
        :class="`archetype-${entry.archetype}`"
        :data-fresh="i === 0"
      >
        <span class="meta">
          [{{ entry.archetype }} · {{ entry.district_id }} ·
          t={{ formatTime(entry.hour, entry.minute) }}]
        </span>
        <span class="text">"{{ truncate(entry.post_text) }}"</span>
      </li>
      <li v-if="visibleEntries.length === 0" class="empty-row">
        Waiting for first agent decision&hellip;
      </li>
    </ul>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useGsap } from '@/design/useGsap'

const props = defineProps({
  decisions: { type: Array, default: () => [] }, // [{archetype, district_id, hour, minute, post_text, timestamp}]
  maxVisible: { type: Number, default: 3 },
})

const root = ref(null)
const { ctx, gsap } = useGsap(root)

const reduceMotion = () =>
  typeof window !== 'undefined' &&
  window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

const visibleEntries = computed(() => props.decisions.slice(0, props.maxVisible))

function formatTime(hour, minute) {
  const h = String(hour ?? 0).padStart(2, '0')
  const m = String(minute ?? 0).padStart(2, '0')
  return `${h}:${m}`
}

function truncate(s, n = 80) {
  if (!s) return ''
  return s.length > n ? s.slice(0, n - 1) + '…' : s
}

let lastFirst = null
watch(
  () => props.decisions[0]?.timestamp + props.decisions[0]?.post_text,
  async (key) => {
    if (!key || key === lastFirst) return
    lastFirst = key
    if (reduceMotion()) return
    await nextTick()
    const newRow = root.value?.querySelector('.ticker-row[data-fresh="true"]')
    if (!newRow) return
    ctx.value?.add(() => {
      gsap.from(newRow, {
        y: -16,
        opacity: 0,
        duration: 0.3,
        ease: 'power2.out',
      })
    })
  },
)

onMounted(() => {
  // First mount with seeded data — no animation
  lastFirst = props.decisions[0]?.timestamp + props.decisions[0]?.post_text
})
</script>

<style scoped>
.agent-log-ticker {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  padding: var(--sp-3) var(--sp-4);
  background: var(--bg-1);
  border: 1px solid var(--line);
  border-radius: 10px;
  font-family: 'JetBrains Mono', 'SF Mono', ui-monospace, monospace;
  font-size: var(--fz-12);
  color: var(--ink-1);
}
.ticker-header {
  display: flex;
  justify-content: space-between;
  font-family: 'Inter Variable', Inter, sans-serif;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--ink-2);
  font-weight: 600;
}
.ticker-title {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-1);
}
.ticker-title::before {
  content: '';
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--el-aether);
  box-shadow: 0 0 6px var(--el-aether);
  animation: pulse 1.6s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.8); }
}

.ticker-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
  min-height: calc(3 * 1.6em + 2 * var(--sp-1));
}
.ticker-list.empty {
  justify-content: center;
}
.ticker-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-1);
  line-height: 1.5;
}
.ticker-row .meta {
  color: var(--ink-2);
  font-weight: 500;
  white-space: nowrap;
}
.ticker-row .text {
  color: var(--ink-0);
  flex: 1;
}
.empty-row {
  color: var(--ink-2);
  font-style: italic;
}

/* Subtle archetype color hint on the first chip */
.archetype-eyewitness .meta { color: var(--el-fire); }
.archetype-helper .meta { color: var(--el-aether); }
.archetype-amplifier .meta { color: var(--el-water); }
.archetype-authority .meta { color: var(--el-air); }
.archetype-vulnerable .meta { color: var(--el-earth); }

@media (prefers-reduced-motion: reduce) {
  .ticker-title::before {
    animation: none;
  }
}
</style>
