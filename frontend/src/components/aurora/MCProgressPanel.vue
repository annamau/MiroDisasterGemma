<template>
  <div ref="root" class="mc-progress-panel" role="status" aria-live="polite">
    <div class="panel-header">
      <span class="panel-title">Running Monte Carlo</span>
      <span class="panel-meta">{{ overallText }}</span>
    </div>
    <div
      v-for="arm in arms"
      :key="arm.intervention_id"
      class="arm-row"
      :class="`element-${arm.element || 'aether'}`"
    >
      <div class="arm-label">
        <ElementBadge :element="arm.element || 'aether'" :icon="arm.icon || 'Siren'" :size="20" />
        <span class="arm-text">{{ arm.label }}</span>
      </div>
      <div class="bar-track">
        <div
          class="bar-fill"
          :ref="(el) => barRefs[arm.intervention_id] = el"
          :style="{
            background: `var(--el-${arm.element || 'aether'})`,
            color: `var(--el-${arm.element || 'aether'})`,
          }"
          :aria-label="`${arm.label}: ${pctOf(arm.intervention_id)}% complete`"
        ></div>
      </div>
      <div class="arm-stats">
        <span class="counter">{{ doneOf(arm.intervention_id) }}/{{ totalOf(arm.intervention_id) }}</span>
        <span class="mean" v-if="meanOf(arm.intervention_id) !== null">
          mean deaths: {{ meanOf(arm.intervention_id).toFixed(1) }}
        </span>
      </div>
    </div>
    <div v-if="error" class="panel-error">{{ error }}</div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { auroraApi } from '@/api/aurora'
import { useGsap } from '@/design/useGsap'
import ElementBadge from './ElementBadge.vue'

const props = defineProps({
  runId: { type: String, default: null },
  scenarioId: { type: String, default: '' },
  arms: { type: Array, required: true },
  pollInterval: { type: Number, default: 500 },
  // Sandbox / offline-mock support: when provided, these bypass polling and
  // drive the panel directly. Useful for the dev sandbox demo.
  mockArmState: { type: Object, default: null },
  mockError: { type: String, default: null },
})

const emit = defineEmits(['done', 'progress', 'error'])

const root = ref(null)
const barRefs = ref({})
const armState = ref({}) // intervention_id -> { trials_done, trials_total, deaths_running_mean }
const recentDecisions = ref([])
const error = ref(props.mockError ?? null)
const isDone = ref(false)
let timer = null

const { ctx, gsap } = useGsap(root)

const reduceMotion = () =>
  typeof window !== 'undefined' &&
  window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

function doneOf(armId) {
  return armState.value[armId]?.trials_done ?? 0
}
function totalOf(armId) {
  return armState.value[armId]?.trials_total ?? props.arms.find((a) => a.intervention_id === armId)?.n_trials ?? 0
}
function meanOf(armId) {
  const m = armState.value[armId]?.deaths_running_mean
  return typeof m === 'number' ? m : null
}
function pctOf(armId) {
  const total = totalOf(armId)
  if (!total) return 0
  return Math.min(100, Math.round((doneOf(armId) / total) * 100))
}

const overallText = computed(() => {
  const totals = props.arms.reduce(
    (acc, a) => {
      acc.done += doneOf(a.intervention_id)
      acc.total += totalOf(a.intervention_id)
      return acc
    },
    { done: 0, total: 0 },
  )
  if (!totals.total) return ''
  return `${totals.done}/${totals.total} trials`
})

function applyBarWidth(armId, pct) {
  const el = barRefs.value[armId]
  if (!el) return
  if (reduceMotion()) {
    el.style.width = `${pct}%`
    return
  }
  // Smooth width tween via GSAP, registered with the context for cleanup.
  ctx.value?.add(() => {
    gsap.to(el, { width: `${pct}%`, duration: 0.4, ease: 'power2.out', overwrite: true })
  })
}

async function poll() {
  if (!props.runId) return
  try {
    const { data } = await auroraApi.getMCProgress(props.scenarioId, props.runId)
    if (!data?.success) {
      error.value = data?.error || 'progress fetch failed'
      emit('error', error.value)
      stopPolling()
      return
    }
    const payload = data.data
    armState.value = { ...payload.arms }
    recentDecisions.value = payload.recent_decisions || []
    emit('progress', { arms: payload.arms, recent_decisions: payload.recent_decisions })

    // Apply bar widths
    for (const arm of props.arms) {
      applyBarWidth(arm.intervention_id, pctOf(arm.intervention_id))
    }

    if (payload.error) {
      error.value = payload.error
      emit('error', payload.error)
      stopPolling()
      return
    }
    if (payload.done && !isDone.value) {
      isDone.value = true
      stopPolling()
      // Fetch the final result and emit it up
      try {
        const { data: rdata } = await auroraApi.getMCResult(props.scenarioId, props.runId)
        if (rdata?.success) {
          emit('done', rdata.data)
        } else {
          error.value = rdata?.error || 'result fetch failed'
          emit('error', error.value)
        }
      } catch (e) {
        error.value = e.message
        emit('error', e.message)
      }
    }
  } catch (e) {
    error.value = e.message
    emit('error', e.message)
  }
}

function startPolling() {
  stopPolling()
  if (!props.runId) return
  isDone.value = false
  poll()
  timer = setInterval(poll, props.pollInterval)
}
function stopPolling() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

watch(
  () => props.runId,
  (id) => {
    if (id) startPolling()
    else stopPolling()
  },
)

// Mock-driven mode: assign armState immediately so template counters
// render correctly on first paint, then apply DOM widths after nextTick
// once template refs (barRefs) have been populated.
watch(
  () => props.mockArmState,
  async (mock) => {
    if (!mock) return
    armState.value = { ...mock }
    await nextTick()
    for (const arm of props.arms) {
      applyBarWidth(arm.intervention_id, pctOf(arm.intervention_id))
    }
  },
  { deep: true, immediate: true },
)
watch(
  () => props.mockError,
  (e) => {
    if (e) error.value = e
  },
)

onMounted(() => {
  if (props.runId) startPolling()
})
onBeforeUnmount(() => {
  stopPolling()
})

defineExpose({ recentDecisions })
</script>

<style scoped>
.mc-progress-panel {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  padding: var(--sp-4);
  background: var(--bg-1);
  border: 1px solid var(--line);
  border-radius: 10px;
}
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: var(--sp-2);
}
.panel-title {
  font-size: var(--fz-14);
  font-weight: 600;
  color: var(--ink-0);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.panel-meta {
  font-size: var(--fz-12);
  color: var(--ink-1);
  font-variant-numeric: tabular-nums;
}
.arm-row {
  display: grid;
  grid-template-columns: minmax(160px, 1fr) 2fr auto;
  gap: var(--sp-3);
  align-items: center;
}
.arm-label {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-width: 0;
}
.arm-text {
  font-size: var(--fz-14);
  color: var(--ink-0);
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.bar-track {
  position: relative;
  height: 6px;
  background: var(--bg-2);
  border-radius: 3px;
  overflow: hidden;
}
.bar-fill {
  position: absolute;
  top: 0;
  left: 0;
  bottom: 0;
  width: 0;
  border-radius: 3px;
  filter: drop-shadow(0 0 6px currentColor);
  transition: background 0.2s ease;
}
.arm-stats {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  font-size: var(--fz-12);
  font-variant-numeric: tabular-nums;
  color: var(--ink-1);
  min-width: 110px;
}
.counter {
  font-weight: 600;
  color: var(--ink-0);
}
.mean {
  color: var(--ink-2);
  font-size: 11px;
}
.panel-error {
  font-size: var(--fz-12);
  color: var(--el-fire);
  background: rgba(242, 92, 31, 0.1);
  padding: var(--sp-2) var(--sp-3);
  border-radius: 6px;
}

@media (prefers-reduced-motion: reduce) {
  .bar-fill {
    transition: none;
  }
}
</style>
