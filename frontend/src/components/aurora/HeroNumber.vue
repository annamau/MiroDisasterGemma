<template>
  <div ref="root" class="hero-number" :class="`element-${element || 'aether'}`">
    <div class="value-row">
      <span class="prefix" v-if="prefix">{{ prefix }}</span>
      <span class="value">{{ displayValue }}</span>
      <span class="unit" v-if="unit">{{ unit }}</span>
    </div>
    <div class="label">{{ label }}</div>
    <div class="ci" v-if="ci && (ci.lo !== undefined || ci.hi !== undefined)">
      90% CI [{{ formatCi(ci.lo) }}, {{ formatCi(ci.hi) }}]
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useGsap } from '@/design/useGsap'
import { DUR, EASES } from '@/design/motion'

const props = defineProps({
  value: { type: Number, required: true },
  label: { type: String, required: true },
  ci: { type: Object, default: null }, // { lo, hi }
  unit: { type: String, default: '' },
  prefix: { type: String, default: '' },
  element: { type: String, default: 'aether' },
  fractionDigits: { type: Number, default: 0 },
  // Format the value with K/M abbreviations when above thresholds.
  abbrev: { type: Boolean, default: false },
})

const root = ref(null)
const { ctx, gsap } = useGsap(root)
const animatedValue = ref(0)

const reduceMotion = () =>
  typeof window !== 'undefined' &&
  window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

function formatNumber(n) {
  if (!Number.isFinite(n)) return '—'
  if (props.abbrev) {
    const abs = Math.abs(n)
    if (abs >= 1e9) return (n / 1e9).toFixed(2) + 'B'
    if (abs >= 1e6) return (n / 1e6).toFixed(2) + 'M'
    if (abs >= 1e3) return (n / 1e3).toFixed(1) + 'K'
  }
  return new Intl.NumberFormat('en-US', {
    maximumFractionDigits: props.fractionDigits,
    minimumFractionDigits: 0,
  }).format(n)
}

function formatCi(n) {
  if (!Number.isFinite(n)) return '—'
  return formatNumber(n)
}

const displayValue = computed(() => formatNumber(animatedValue.value))

function tweenTo(target) {
  if (reduceMotion()) {
    animatedValue.value = target
    return
  }
  ctx.value?.add(() => {
    gsap.to(animatedValue, {
      value: target,
      duration: DUR.hero,
      ease: EASES.out,
      overwrite: true,
    })
  })
}

watch(
  () => props.value,
  (v) => tweenTo(v),
)

onMounted(() => tweenTo(props.value))
</script>

<style scoped>
.hero-number {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}
.value-row {
  display: inline-flex;
  align-items: baseline;
  gap: var(--sp-2);
  font-size: var(--fz-64);
  font-weight: 700;
  line-height: 1;
  color: var(--ink-0);
  font-feature-settings: 'tnum' 1, 'ss01' 1;
}
.value {
  display: inline-block;
}
.element-fire .value { color: var(--el-fire); }
.element-water .value { color: var(--el-water); }
.element-earth .value { color: var(--el-earth); }
.element-air .value { color: var(--el-air); }
.element-aether .value { color: var(--el-aether); }

.prefix, .unit {
  font-size: var(--fz-24);
  font-weight: 600;
  color: var(--ink-1);
}
.label {
  font-size: var(--fz-14);
  color: var(--ink-1);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: 600;
}
.ci {
  font-size: var(--fz-12);
  color: var(--ink-2);
  font-variant-numeric: tabular-nums;
}
</style>
