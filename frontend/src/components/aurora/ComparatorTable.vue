<template>
  <div ref="root" class="comparator-table" role="table" :aria-label="ariaLabel">
    <div class="cmp-header" role="row">
      <div role="columnheader" class="col-label">Intervention</div>
      <div role="columnheader" class="col-bar">Lives saved (with 90% CI)</div>
      <div role="columnheader" class="col-num">Mean</div>
    </div>
    <div
      v-for="(arm, idx) in armsRanked"
      :key="arm.intervention_id"
      class="cmp-row"
      :class="`element-${arm.element || 'aether'}`"
      role="row"
    >
      <div class="col-label" role="cell">
        <ElementBadge
          :element="arm.element || 'aether'"
          :icon="arm.icon || 'Siren'"
          :size="20"
        />
        <span class="label-text">{{ arm.label }}</span>
      </div>
      <div class="col-bar" role="cell">
        <div class="bar-track">
          <!-- CI overlay (drawn underneath the mean bar) -->
          <div
            class="ci-band"
            :style="ciStyle(arm)"
            :aria-label="`90% CI from ${formatNum(arm.lives_saved_ci?.lo)} to ${formatNum(arm.lives_saved_ci?.hi)}`"
          ></div>
          <!-- Mean bar -->
          <div
            class="mean-bar"
            :ref="(el) => barRefs[arm.intervention_id] = el"
            :data-arm="arm.intervention_id"
            :style="{
              background: `var(--el-${arm.element || 'aether'})`,
              color: `var(--el-${arm.element || 'aether'})`,
            }"
          ></div>
        </div>
      </div>
      <div class="col-num" role="cell">
        <div class="mean-num">{{ formatNum(arm.lives_saved_mean) }}</div>
        <div class="ci-num" v-if="arm.lives_saved_ci">
          [{{ formatNum(arm.lives_saved_ci.lo) }},
          {{ formatNum(arm.lives_saved_ci.hi) }}]
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useGsap } from '@/design/useGsap'
import { DUR, EASES } from '@/design/motion'
import ElementBadge from './ElementBadge.vue'

const props = defineProps({
  arms: { type: Array, required: true },
  /* arm shape:
     { intervention_id, label, element, icon,
       lives_saved_mean, lives_saved_ci: {lo, hi} }
  */
  ariaLabel: { type: String, default: 'Intervention comparator table' },
})

const root = ref(null)
const barRefs = ref({})
const { ctx, gsap } = useGsap(root)

const reduceMotion = () =>
  typeof window !== 'undefined' &&
  window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

// Sort by mean (largest first) so the wow card lands at the top.
const armsRanked = computed(() =>
  [...props.arms].sort(
    (a, b) => (b.lives_saved_mean || 0) - (a.lives_saved_mean || 0),
  ),
)

const maxMean = computed(() => {
  const ms = props.arms.map((a) => a.lives_saved_mean || 0)
  return Math.max(...ms, 1)
})

const maxCiHi = computed(() => {
  const hs = props.arms.map((a) => a.lives_saved_ci?.hi || 0)
  return Math.max(maxMean.value, ...hs, 1)
})

function pctOf(value) {
  return Math.max(0, Math.min(100, (value / maxCiHi.value) * 100))
}

function ciStyle(arm) {
  if (!arm.lives_saved_ci) return { display: 'none' }
  const loPct = pctOf(arm.lives_saved_ci.lo || 0)
  const hiPct = pctOf(arm.lives_saved_ci.hi || 0)
  // CI band uses the tokenized `--line` color at higher alpha so it remains
  // visible on dark + light themes without drift if the palette is rebranded.
  return {
    left: `${loPct}%`,
    width: `${Math.max(0, hiPct - loPct)}%`,
    background: 'color-mix(in srgb, var(--line) 60%, transparent)',
  }
}

function formatNum(n) {
  if (!Number.isFinite(n)) return '—'
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(n)
}

function applyBarWidths(animate = true) {
  for (const arm of armsRanked.value) {
    const el = barRefs.value[arm.intervention_id]
    if (!el) continue
    const pct = pctOf(arm.lives_saved_mean || 0)
    if (animate && !reduceMotion()) {
      ctx.value?.add(() => {
        gsap.fromTo(
          el,
          { width: '0%' },
          { width: `${pct}%`, duration: DUR.slow, ease: EASES.snappy, overwrite: true },
        )
      })
    } else {
      el.style.width = `${pct}%`
    }
  }
}

watch(
  () => props.arms,
  async () => {
    await nextTick()
    applyBarWidths(true)
  },
  { deep: true },
)

onMounted(async () => {
  await nextTick()
  applyBarWidths(true)
})
</script>

<style scoped>
.comparator-table {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  background: var(--bg-1);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: var(--sp-4);
}
.cmp-header,
.cmp-row {
  display: grid;
  grid-template-columns: minmax(200px, 1.2fr) 3fr minmax(120px, auto);
  gap: var(--sp-3);
  align-items: center;
}
.cmp-header {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--ink-2);
  font-weight: 600;
  padding-bottom: var(--sp-2);
  border-bottom: 1px solid var(--line);
}
.cmp-row {
  padding: var(--sp-2) 0;
}
.cmp-row + .cmp-row {
  border-top: 1px solid var(--line);
}

.col-label {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-width: 0;
}
.label-text {
  color: var(--ink-0);
  font-weight: 500;
  font-size: var(--fz-14);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.col-bar {
  min-width: 0;
}
.bar-track {
  position: relative;
  height: 18px;
  background: var(--bg-2);
  border-radius: 4px;
  overflow: hidden;
}
.ci-band {
  position: absolute;
  top: 0;
  bottom: 0;
  border-radius: 4px;
}
.mean-bar {
  position: absolute;
  top: 4px;
  bottom: 4px;
  left: 0;
  width: 0;
  border-radius: 3px;
  filter: drop-shadow(0 0 6px currentColor);
}

.col-num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.mean-num {
  font-size: var(--fz-16);
  font-weight: 700;
  color: var(--ink-0);
}
.ci-num {
  font-size: 11px;
  color: var(--ink-2);
}

@media (prefers-reduced-motion: reduce) {
  .mean-bar {
    transition: none;
  }
}
</style>
