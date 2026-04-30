<template>
  <figure ref="root" class="cumulative-chart">
    <figcaption class="chart-title">{{ title }}</figcaption>
    <svg
      :viewBox="`0 0 ${width} ${height}`"
      :width="width"
      :height="height"
      role="img"
      :aria-label="ariaLabel"
    >
      <!-- y grid lines (fade in last) -->
      <g ref="grid" class="grid" :opacity="0">
        <line
          v-for="t in yTicks"
          :key="`gy${t}`"
          :x1="margin.left"
          :x2="width - margin.right"
          :y1="yScale(t)"
          :y2="yScale(t)"
          stroke="var(--line)"
          stroke-dasharray="2,4"
        />
        <text
          v-for="t in yTicks"
          :key="`yt${t}`"
          :x="margin.left - 8"
          :y="yScale(t)"
          text-anchor="end"
          dominant-baseline="middle"
          class="tick-label"
        >{{ formatNum(t) }}</text>
        <text
          v-for="t in xTicks"
          :key="`xt${t}`"
          :x="xScale(t)"
          :y="height - margin.bottom + 18"
          text-anchor="middle"
          class="tick-label"
        >{{ t }}h</text>
      </g>

      <!-- one path per arm -->
      <g class="paths">
        <path
          v-for="(arm, idx) in pathArms"
          :key="arm.intervention_id"
          :ref="(el) => pathRefs[arm.intervention_id] = el"
          :d="arm.d"
          :stroke="`var(--el-${arm.element || 'aether'})`"
          stroke-width="2"
          fill="none"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </g>

      <!-- end-point label dots -->
      <g class="end-labels">
        <g
          v-for="arm in pathArms"
          :key="arm.intervention_id + '-label'"
          class="end-label"
          :ref="(el) => labelRefs[arm.intervention_id] = el"
          :opacity="0"
        >
          <circle
            :cx="arm.endX"
            :cy="arm.endY"
            r="3"
            :fill="`var(--el-${arm.element || 'aether'})`"
          />
          <text
            :x="arm.endX + 6"
            :y="arm.endY"
            dominant-baseline="middle"
            class="end-label-text"
            :fill="`var(--el-${arm.element || 'aether'})`"
          >{{ arm.label }}</text>
        </g>
      </g>
    </svg>
    <figcaption class="chart-footer">
      Cumulative mean across {{ nTrials }} trials. Damage states from HAZUS-MH
      2.1; ground motion via Worden 2012 GMICE.
    </figcaption>
  </figure>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import * as d3 from 'd3'
import { useGsap } from '@/design/useGsap'
import { DUR, EASES } from '@/design/motion'

const props = defineProps({
  arms: { type: Array, required: true },
  /* arm shape: { intervention_id, label, element, cumulative_deaths_mean: number[] }
     The series is the cumulative MEAN across trials (sum of per-hour mean deaths),
     not the median p50 path. Footer attribution reflects this honestly. */
  width: { type: Number, default: 760 },
  height: { type: Number, default: 280 },
  nTrials: { type: Number, default: 0 },
  title: { type: String, default: 'Cumulative deaths over time (mean across trials)' },
  ariaLabel: { type: String, default: 'Cumulative mean deaths timeline by intervention' },
})

const root = ref(null)
const grid = ref(null)
const pathRefs = ref({})
const labelRefs = ref({})

const { ctx, gsap } = useGsap(root)

const reduceMotion = () =>
  typeof window !== 'undefined' &&
  window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

const margin = { top: 16, right: 96, bottom: 28, left: 48 }

// Domain
const allHours = computed(() => {
  const lengths = props.arms.map((a) => (a.cumulative_deaths_mean || []).length)
  return Math.max(...lengths, 1)
})
const allDeaths = computed(() => {
  const series = props.arms.flatMap((a) => a.cumulative_deaths_mean || [])
  return Math.max(...series, 1)
})

// Scales
const xScale = computed(() =>
  d3.scaleLinear()
    .domain([0, allHours.value - 1])
    .range([margin.left, props.width - margin.right]),
)
const yScale = computed(() =>
  d3.scaleLinear()
    .domain([0, allDeaths.value])
    .nice()
    .range([props.height - margin.bottom, margin.top]),
)

const yTicks = computed(() => yScale.value.ticks(4))
const xTicks = computed(() => xScale.value.ticks(6).filter((t) => Number.isInteger(t)))

const pathArms = computed(() => {
  const line = d3.line()
    .x((_, i) => xScale.value(i))
    .y((d) => yScale.value(d))
    .curve(d3.curveMonotoneX)

  return props.arms.map((arm) => {
    const series = arm.cumulative_deaths_mean || []
    const d = series.length ? line(series) : ''
    const lastIdx = series.length - 1
    return {
      ...arm,
      d,
      endX: lastIdx >= 0 ? xScale.value(lastIdx) : 0,
      endY: lastIdx >= 0 ? yScale.value(series[lastIdx]) : 0,
    }
  })
})

function formatNum(n) {
  if (!Number.isFinite(n)) return '—'
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(n)
}

async function animateReveal() {
  await nextTick()
  if (reduceMotion()) {
    // No animation — just render statically with full opacity
    if (grid.value) grid.value.setAttribute('opacity', '1')
    Object.values(labelRefs.value).forEach((el) => {
      if (el) el.setAttribute('opacity', '1')
    })
    return
  }
  ctx.value?.add(() => {
    // 1) Each path draws via stroke-dashoffset → 0 with stagger.
    const pathEntries = pathArms.value
      .map((arm) => ({ id: arm.intervention_id, el: pathRefs.value[arm.intervention_id] }))
      .filter((e) => e.el)
    pathEntries.forEach(({ el }, i) => {
      const len = el.getTotalLength?.() || 1000
      gsap.set(el, { strokeDasharray: len, strokeDashoffset: len })
      gsap.to(el, {
        strokeDashoffset: 0,
        duration: DUR.slow,
        ease: EASES.out,
        delay: i * 0.15,
      })
      // End-label fades in after the path
      const labelEl = labelRefs.value[pathEntries[i].id]
      if (labelEl) {
        gsap.to(labelEl, {
          opacity: 1,
          duration: DUR.base,
          ease: EASES.out,
          delay: i * 0.15 + DUR.slow * 0.7,
        })
      }
    })
    // 2) Grid fades in last
    if (grid.value) {
      gsap.to(grid.value, {
        opacity: 1,
        duration: DUR.base,
        ease: EASES.out,
        delay: pathEntries.length * 0.15 + DUR.slow * 0.4,
      })
    }
  })
}

watch(() => props.arms, animateReveal, { deep: true })
onMounted(animateReveal)
</script>

<style scoped>
.cumulative-chart {
  margin: 0;
  background: var(--bg-1);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: var(--sp-4);
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}
.chart-title {
  font-size: var(--fz-14);
  font-weight: 600;
  color: var(--ink-1);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
svg {
  display: block;
  width: 100%;
  height: auto;
  max-width: 100%;
}
.tick-label {
  font-size: 10px;
  fill: var(--ink-2);
  font-variant-numeric: tabular-nums;
}
.end-label-text {
  font-size: 11px;
  font-weight: 600;
}
.chart-footer {
  font-size: 11px;
  color: var(--ink-2);
  border-top: 1px solid var(--line);
  padding-top: var(--sp-2);
  margin-top: var(--sp-2);
  font-style: italic;
}
</style>
