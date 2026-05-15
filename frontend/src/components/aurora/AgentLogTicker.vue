<!-- SPDX-License-Identifier: Apache-2.0 -->
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
        <img
          class="avatar"
          :src="avatarFor(entry)"
          :alt="`${entry.agent_name || entry.archetype} avatar`"
          loading="lazy"
        />
        <div class="post">
          <div class="post-head">
            <span class="agent-name">{{ entry.agent_name || labelize(entry.archetype) }}</span>
            <span class="agent-handle" v-if="entry.agent_handle">{{ entry.agent_handle }}</span>
            <span class="role-chip" :class="`archetype-chip-${entry.archetype}`">
              {{ entry.agent_role || labelize(entry.archetype) }}
            </span>
            <span class="meta-dot">·</span>
            <span class="meta-loc">{{ entry.district_id }}</span>
            <span class="meta-dot">·</span>
            <span class="meta-time">t+{{ formatTime(entry.hour, entry.minute) }}</span>
          </div>
          <div class="post-text">{{ truncate(entry.post_text) }}</div>
        </div>
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

function truncate(s, n = 140) {
  if (!s) return ''
  return s.length > n ? s.slice(0, n - 1) + '…' : s
}

function labelize(archetype) {
  if (!archetype) return 'Agent'
  return archetype.charAt(0).toUpperCase() + archetype.slice(1)
}

// Deterministic per-handle hash → hue. Same person always gets same color.
function hashStr(s) {
  let h = 0
  for (let i = 0; i < s.length; i++) {
    h = (h << 5) - h + s.charCodeAt(i)
    h |= 0
  }
  return Math.abs(h)
}

function initialsFor(entry) {
  const name = entry.agent_name || entry.archetype || '?'
  const parts = name.split(/\s+/).filter(Boolean)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

// Inline SVG avatar — initials on a stable colored disc.
// Offline-safe (no external CDN), zero load time, and the seed makes
// the same handle always render the same gradient.
function avatarFor(entry) {
  const seed = entry.avatar_seed || entry.agent_handle || entry.archetype || 'agent'
  const hue = hashStr(seed) % 360
  const bg1 = `hsl(${hue}, 60%, 52%)`
  const bg2 = `hsl(${(hue + 35) % 360}, 65%, 42%)`
  const initials = initialsFor(entry)
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
    <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="${bg1}"/>
      <stop offset="100%" stop-color="${bg2}"/>
    </linearGradient></defs>
    <circle cx="32" cy="32" r="32" fill="url(#g)"/>
    <text x="32" y="38" text-anchor="middle"
          font-family="Inter, system-ui, sans-serif"
          font-weight="700" font-size="24" fill="white">${initials}</text>
  </svg>`
  return 'data:image/svg+xml;utf8,' + encodeURIComponent(svg)
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
  gap: var(--sp-2);
  min-height: calc(3 * 3.4em);
}
.ticker-list.empty {
  justify-content: center;
}
.ticker-row {
  display: grid;
  grid-template-columns: 36px 1fr;
  gap: var(--sp-3);
  align-items: flex-start;
  padding: var(--sp-2) 0;
  border-bottom: 1px solid var(--line);
}
.ticker-row:last-child { border-bottom: none; }

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  flex-shrink: 0;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.18);
}

.post {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.post-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  font-family: 'Inter Variable', Inter, sans-serif;
  font-size: var(--fz-12);
}
.agent-name {
  color: var(--ink-0);
  font-weight: 700;
}
.agent-handle {
  color: var(--ink-2);
  font-weight: 500;
}
.role-chip {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  background: var(--bg-2);
  color: var(--ink-1);
  border: 1px solid var(--line);
}
.meta-dot { color: var(--ink-2); }
.meta-loc, .meta-time {
  color: var(--ink-2);
  font-variant-numeric: tabular-nums;
}
.post-text {
  color: var(--ink-0);
  font-family: 'Inter Variable', Inter, sans-serif;
  font-size: var(--fz-14);
  line-height: 1.4;
}

.empty-row {
  color: var(--ink-2);
  font-style: italic;
  padding: var(--sp-3) 0;
  text-align: center;
}

/* Archetype-tinted role chips */
.archetype-chip-eyewitness  { background: rgba(242, 92, 31, 0.12);  color: var(--el-fire);   border-color: rgba(242, 92, 31, 0.32); }
.archetype-chip-helper      { background: rgba(120, 209, 196, 0.12);color: var(--el-aether); border-color: rgba(120, 209, 196, 0.36);}
.archetype-chip-amplifier   { background: rgba(75, 156, 211, 0.12); color: var(--el-water);  border-color: rgba(75, 156, 211, 0.34); }
.archetype-chip-authority   { background: rgba(168, 199, 250, 0.14);color: var(--el-air);    border-color: rgba(168, 199, 250, 0.38);}
.archetype-chip-vulnerable  { background: rgba(180, 138, 78, 0.14); color: var(--el-earth);  border-color: rgba(180, 138, 78, 0.36); }

@media (prefers-reduced-motion: reduce) {
  .ticker-title::before {
    animation: none;
  }
}
</style>
