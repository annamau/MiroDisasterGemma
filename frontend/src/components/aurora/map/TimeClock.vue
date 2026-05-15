<!-- SPDX-License-Identifier: Apache-2.0 -->
<!--
  TimeClock: small HUD overlay shown on the map during replay. Renders
  "t + hh:mm  ·  N% of M-hour replay". Hidden when no replay is in
  progress (animationHour < 0 or replay finished).
-->
<template>
  <div v-if="visible" class="time-clock" :data-active="active">
    <div class="tc-clock">
      <span class="tc-prefix">t +</span>
      <span class="tc-hhmm">{{ hhmm }}</span>
    </div>
    <div class="tc-bar">
      <div class="tc-bar-fill" :style="{ width: `${pct}%` }"></div>
    </div>
    <div class="tc-meta">{{ pct }}% · {{ totalHours }}h replay</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  /** Current playback hour. -1 = pre-replay (don't show). */
  animationHour: { type: Number, default: -1 },
  /** Replay duration in hours. */
  totalHours: { type: Number, default: 24 },
})

const visible = computed(() => props.animationHour >= 0)
const active = computed(() => props.animationHour > 0 && props.animationHour < props.totalHours)

const pct = computed(() => {
  if (!props.totalHours) return 0
  const r = props.animationHour / props.totalHours
  return Math.min(100, Math.max(0, Math.round(r * 100)))
})

const hhmm = computed(() => {
  const totalMinutes = props.animationHour * 60
  const hh = Math.floor(totalMinutes / 60)
  const mm = Math.floor(totalMinutes % 60)
  return `${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}`
})
</script>

<style scoped>
.time-clock {
  position: absolute;
  top: var(--sp-3);
  right: var(--sp-3);
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 6px 10px 8px;
  background: color-mix(in srgb, var(--bg-2) 92%, transparent);
  border: 1px solid var(--line);
  border-radius: 8px;
  font-family: 'JetBrains Mono', 'SF Mono', ui-monospace, monospace;
  font-size: 11px;
  color: var(--ink-0);
  backdrop-filter: blur(6px);
  box-shadow: 0 4px 14px -6px rgba(26, 34, 56, 0.18);
  pointer-events: none;
  z-index: 3;
  min-width: 116px;
}
.tc-clock {
  display: flex;
  align-items: baseline;
  gap: 4px;
}
.tc-prefix {
  font-size: 10px;
  color: var(--ink-2);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.tc-hhmm {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0.02em;
  font-variant-numeric: tabular-nums;
  color: var(--ink-0);
}
.tc-bar {
  position: relative;
  height: 3px;
  background: var(--bg-2);
  border-radius: 2px;
  overflow: hidden;
}
.tc-bar-fill {
  position: absolute;
  inset: 0;
  width: 0;
  background: linear-gradient(90deg, var(--el-fire), var(--el-water));
  border-radius: 2px;
  transition: width 0.45s ease-out;
}
.tc-meta {
  font-size: 10px;
  color: var(--ink-2);
  font-variant-numeric: tabular-nums;
}
/* "Active" pulse — subtle indicator that the clock is ticking. */
@keyframes tcActivePulse {
  0%, 100% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--el-fire) 50%, transparent); }
  50%      { box-shadow: 0 0 0 4px color-mix(in srgb, var(--el-fire) 0%, transparent); }
}
.time-clock[data-active="true"] {
  animation: tcActivePulse 1.6s ease-in-out infinite;
}
@media (prefers-reduced-motion: reduce) {
  .time-clock[data-active="true"] { animation: none; }
  .tc-bar-fill { transition: none; }
}
</style>
