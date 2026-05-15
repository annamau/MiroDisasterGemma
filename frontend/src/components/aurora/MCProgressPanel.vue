<!-- SPDX-License-Identifier: Apache-2.0 -->
<template>
  <div ref="root" class="mc-progress-panel" role="status" aria-live="polite">
    <div class="panel-header">
      <div class="title-block">
        <span class="panel-title">Running Monte Carlo</span>
        <span class="panel-sub">Gemma 4 deciding · {{ arms.length }} arm<span v-if="arms.length !== 1">s</span></span>
      </div>
      <div class="overall-block">
        <span class="overall-count">{{ overallDone }}<span class="of">/{{ overallTotal }}</span></span>
        <span class="overall-label">trials</span>
      </div>
    </div>

    <div class="overall-bar" :aria-label="`Overall progress: ${overallPct}%`">
      <div class="overall-fill" :style="{ width: `${overallPct}%` }"></div>
    </div>

    <div
      v-for="arm in arms"
      :key="arm.intervention_id"
      class="arm-row"
      :class="`element-${arm.element || 'aether'}`"
    >
      <div class="arm-label">
        <ElementBadge :element="arm.element || 'aether'" :icon="arm.icon || 'Siren'" :size="20" />
        <div class="arm-text-block">
          <span class="arm-text">{{ arm.label }}</span>
          <span class="arm-sub" v-if="meanOf(arm.intervention_id) !== null">
            mean deaths so far: <strong>{{ Math.round(meanOf(arm.intervention_id)).toLocaleString() }}</strong>
          </span>
          <span class="arm-sub muted" v-else>waiting for first trial…</span>
        </div>
      </div>
      <div class="arm-progress">
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
        <div class="arm-counter">
          <span class="counter">{{ doneOf(arm.intervention_id) }}/{{ totalOf(arm.intervention_id) }}</span>
          <span class="pct">{{ pctOf(arm.intervention_id) }}%</span>
        </div>
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

const overallTotals = computed(() =>
  props.arms.reduce(
    (acc, a) => {
      acc.done += doneOf(a.intervention_id)
      acc.total += totalOf(a.intervention_id)
      return acc
    },
    { done: 0, total: 0 },
  ),
)
const overallDone = computed(() => overallTotals.value.done)
const overallTotal = computed(() => overallTotals.value.total)
const overallPct = computed(() => {
  const { done, total } = overallTotals.value
  if (!total) return 0
  return Math.min(100, Math.round((done / total) * 100))
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
    // auroraApi.getMCProgress returns the OUTER envelope {success, data: {arms, done, ...}}
    // because the axios interceptor in api/index.js returns res (= response.data) directly.
    // The interceptor already rejects when success===false, but we check here as defense-in-depth.
    const response = await auroraApi.getMCProgress(props.scenarioId, props.runId)
    if (!response?.success) {
      // error may live at the envelope root ({success:false, error:'...'}) or inside data
      error.value = response?.error || response?.data?.error || 'progress fetch failed'
      emit('error', error.value)
      stopPolling()
      return
    }
    const payload = response.data
    // payload is {arms, done, recent_decisions, error}
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
        const rresponse = await auroraApi.getMCResult(props.scenarioId, props.runId)
        if (rresponse?.success) {
          emit('done', rresponse.data)
        } else {
          // mirror getMCProgress: error may live at envelope root or inside data
          error.value = rresponse?.error || rresponse?.data?.error || 'result fetch failed'
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
  align-items: flex-start;
  gap: var(--sp-3);
}
.title-block {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.panel-title {
  font-size: var(--fz-12);
  font-weight: 700;
  color: var(--ink-0);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.panel-sub {
  font-size: 11px;
  color: var(--ink-2);
  font-weight: 500;
}
.overall-block {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  line-height: 1;
}
.overall-count {
  font-family: 'JetBrains Mono', 'SF Mono', ui-monospace, monospace;
  font-size: 22px;
  font-weight: 700;
  color: var(--ink-0);
  font-variant-numeric: tabular-nums;
}
.overall-count .of {
  color: var(--ink-2);
  font-weight: 400;
  font-size: 16px;
}
.overall-label {
  font-size: 10px;
  font-weight: 600;
  color: var(--ink-2);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-top: 4px;
}

.overall-bar {
  position: relative;
  height: 4px;
  background: var(--bg-2);
  border-radius: 2px;
  overflow: hidden;
}
.overall-fill {
  position: absolute;
  inset: 0;
  width: 0;
  background: linear-gradient(90deg, var(--el-aether), var(--el-water));
  border-radius: 2px;
  transition: width 0.4s ease;
}

.arm-row {
  display: grid;
  grid-template-columns: minmax(200px, 1.2fr) 2fr;
  gap: var(--sp-4);
  align-items: center;
  padding: var(--sp-2) 0;
  border-top: 1px dashed var(--line);
}
.arm-label {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-2);
  min-width: 0;
}
.arm-text-block {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.arm-text {
  font-size: var(--fz-14);
  color: var(--ink-0);
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.arm-sub {
  font-size: 11px;
  color: var(--ink-1);
  font-variant-numeric: tabular-nums;
}
.arm-sub.muted { color: var(--ink-2); font-style: italic; }

.arm-progress {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
}
.bar-track {
  position: relative;
  height: 8px;
  flex: 1;
  background: var(--bg-2);
  border-radius: 4px;
  overflow: hidden;
}
.bar-fill {
  position: absolute;
  top: 0;
  left: 0;
  bottom: 0;
  width: 0;
  border-radius: 4px;
  filter: drop-shadow(0 0 6px currentColor);
  transition: background 0.2s ease;
}
.arm-counter {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 1px;
  min-width: 64px;
  font-variant-numeric: tabular-nums;
}
.counter {
  font-size: var(--fz-12);
  font-weight: 600;
  color: var(--ink-0);
}
.pct {
  font-size: 10px;
  color: var(--ink-2);
  font-weight: 600;
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
