<template>
  <div class="aurora" :data-active-element="activeElement" ref="root">
    <header class="hdr">
      <h1>Aurora <span class="hdr-sub">— City Resilience Digital Twin</span></h1>
      <p class="sub">
        Pick a hazard scenario, toggle prevention interventions, run a Monte
        Carlo. Lives saved and dollars saved with 90% confidence intervals.
      </p>
    </header>

    <!-- 1. Scenario picker -->
    <section class="step">
      <div class="step-head">
        <span class="step-num">01</span>
        <h2>Scenario</h2>
      </div>
      <div v-if="!scenarios.length" class="muted">Loading scenarios…</div>
      <div v-else class="scenario-grid">
        <ScenarioCard
          v-for="s in enrichedScenarios"
          :key="s.scenario_id"
          :scenario="s"
          :selected="selectedScenarioId === s.scenario_id"
          @select="selectedScenarioId = $event"
        />
      </div>
      <div class="step-actions">
        <button class="btn ghost" :disabled="loading" @click="onLoadScenario">
          {{ loading ? 'Loading…' : 'Refresh DB' }}
        </button>
      </div>
    </section>

    <!-- 2. Interventions -->
    <section class="step">
      <div class="step-head">
        <span class="step-num">02</span>
        <h2>Interventions</h2>
      </div>
      <div v-if="!interventions.length" class="muted">Loading interventions…</div>
      <div v-else class="chip-grid">
        <InterventionChip
          v-for="iv in enrichedInterventions"
          :key="iv.intervention_id"
          :intervention="iv"
          :selected="selectedInterventionIds.includes(iv.intervention_id)"
          :disabled="iv.intervention_id === 'baseline'"
          @toggle="toggleIntervention"
        />
      </div>
      <div class="cfg-row">
        <label>
          <span>N trials</span>
          <input type="number" v-model.number="nTrials" min="1" max="200" />
        </label>
        <label>
          <span>Population</span>
          <input type="number" v-model.number="nPopulation" min="20" max="500" />
        </label>
        <label>
          <span>Hours</span>
          <input type="number" v-model.number="durationHours" min="6" max="72" />
        </label>
        <label class="ck">
          <input type="checkbox" v-model="useLLM" />
          <span>Use Gemma 4 (e2b) for population decisions</span>
        </label>
      </div>
    </section>

    <!-- 3. Run -->
    <section class="step run-step">
      <div class="step-head">
        <span class="step-num">03</span>
        <h2>Monte Carlo</h2>
      </div>
      <RunButton
        :state="runState"
        :disabled="!canRun || loading"
        @click="onRunMC"
        label="Run Monte Carlo"
      />
      <p v-if="errorMsg" class="err">{{ errorMsg }}</p>
    </section>

    <!-- 4. Streaming progress (visible during run) -->
    <section v-if="streamRunId || runState === 'running'" class="step">
      <div class="step-head">
        <span class="step-num">04</span>
        <h2>Live progress</h2>
      </div>
      <div class="streaming-grid">
        <MCProgressPanel
          :run-id="streamRunId"
          :scenario-id="selectedScenarioId"
          :arms="streamingArms"
          @done="onStreamDone"
          @progress="onStreamProgress"
          @error="onStreamError"
        />
        <AgentLogTicker :decisions="recentDecisions" />
      </div>
    </section>

    <!-- 5. Result reveal (after MC done) -->
    <section v-if="mcRun" class="step result-step">
      <div class="step-head">
        <span class="step-num">05</span>
        <h2>Outcome</h2>
        <span class="meta">
          N={{ mcRun.n_trials }} trials · duration={{ mcRun.duration_hours }}h ·
          wall={{ mcRun.wall_seconds?.toFixed?.(1) ?? mcRun.wall_seconds }}s
        </span>
      </div>

      <!-- Hero numbers -->
      <div class="hero-row" ref="heroRow">
        <HeroNumber
          :value="totalLivesSaved"
          label="Lives saved (best intervention)"
          :ci="bestLivesCi"
          element="aether"
        />
        <HeroNumber
          :value="totalDollarsSaved"
          label="Dollars saved (best intervention)"
          :ci="bestDollarsCi"
          prefix="$"
          element="water"
          :abbrev="true"
        />
      </div>

      <!-- Delta cards (per intervention) -->
      <div class="delta-grid" ref="deltaGrid">
        <DeltaCard
          v-for="d in enrichedDeltas"
          :key="d.intervention_id"
          :delta="d"
        />
      </div>

      <!-- Comparator table -->
      <ComparatorTable :arms="comparatorArms" />

      <!-- Cumulative chart -->
      <CumulativeChart
        :arms="cumulativeArms"
        :n-trials="mcRun.n_trials"
      />
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { auroraApi } from '../api/aurora.js'
import { useGsap } from '@/design/useGsap'
import { DUR, EASES } from '@/design/motion'
import ScenarioCard from '@/components/aurora/ScenarioCard.vue'
import InterventionChip from '@/components/aurora/InterventionChip.vue'
import RunButton from '@/components/aurora/RunButton.vue'
import MCProgressPanel from '@/components/aurora/MCProgressPanel.vue'
import AgentLogTicker from '@/components/aurora/AgentLogTicker.vue'
import HeroNumber from '@/components/aurora/HeroNumber.vue'
import DeltaCard from '@/components/aurora/DeltaCard.vue'
import ComparatorTable from '@/components/aurora/ComparatorTable.vue'
import CumulativeChart from '@/components/aurora/CumulativeChart.vue'

const root = ref(null)
const heroRow = ref(null)
const deltaGrid = ref(null)
const { ctx, gsap } = useGsap(root)

const reduceMotion = () =>
  typeof window !== 'undefined' &&
  window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

// --- State ---
const scenarios = ref([])
const selectedScenarioId = ref('la-puente-hills-m72-ref')
const interventions = ref([])
const selectedInterventionIds = ref([
  'preposition_d03_4amb',
  'evac_d03_30min_early',
  'retrofit_d03_w1',
  'prebunk_misinfo',
])
const nTrials = ref(8)
const nPopulation = ref(80)
const durationHours = ref(24)
const useLLM = ref(false)
const loading = ref(false)
const errorMsg = ref('')

const mcRun = ref(null)
const streamRunId = ref(null)
const runState = ref('idle') // idle | running | done
const recentDecisions = ref([])

// --- Element / icon enrichment for the new visual layer ---
// Disasters → element + Phosphor icon
const SCENARIO_VISUAL = {
  'la-puente-hills-m72-ref': { element: 'earth', icon: 'Mountains' },
  'la-wildfire-santa-ana': { element: 'fire', icon: 'Flame' },
  'socal-flood-arx': { element: 'water', icon: 'WaveTriangle' },
  'hurricane-diana-cat4': { element: 'air', icon: 'Wind' },
  'pop-displacement-aether': { element: 'aether', icon: 'Users' },
}

const INTERVENTION_VISUAL = {
  baseline: { element: 'air', icon: 'Siren' },
  preposition_d03_4amb: { element: 'aether', icon: 'FirstAidKit' },
  evac_d03_30min_early: { element: 'earth', icon: 'ClockClockwise' },
  retrofit_d03_w1: { element: 'earth', icon: 'Buildings' },
  prebunk_misinfo: { element: 'aether', icon: 'ChatCircleDots' },
  fire_break_d03: { element: 'fire', icon: 'Flame' },
}

function visualFor(map, id, fallback = { element: 'aether', icon: 'Siren' }) {
  return map[id] ?? fallback
}

const enrichedScenarios = computed(() =>
  scenarios.value.map((s) => ({
    ...s,
    ...visualFor(SCENARIO_VISUAL, s.scenario_id),
  })),
)
const enrichedInterventions = computed(() =>
  interventions.value.map((iv) => ({
    ...iv,
    ...visualFor(INTERVENTION_VISUAL, iv.intervention_id),
  })),
)

// Page accent retints based on scenario element
const activeElement = computed(() => {
  const v = SCENARIO_VISUAL[selectedScenarioId.value]
  return v?.element ?? 'aether'
})

// --- Computed: streaming arms list ---
const streamingArms = computed(() => {
  const ids = ['baseline', ...selectedInterventionIds.value]
  return ids.map((id) => {
    const iv = interventions.value.find((i) => i.intervention_id === id) || {
      intervention_id: id,
      label: id,
    }
    return {
      ...iv,
      ...visualFor(INTERVENTION_VISUAL, id),
      n_trials: nTrials.value,
    }
  })
})

// --- Computed: result-reveal data ---
const enrichedDeltas = computed(() => {
  if (!mcRun.value) return []
  return mcRun.value.deltas.map((d) => ({
    ...d,
    ...visualFor(INTERVENTION_VISUAL, d.intervention_id),
    lives_saved_mean: d.lives_saved.point,
    lives_saved_ci: { lo: d.lives_saved.lo, hi: d.lives_saved.hi },
    dollars_saved_mean: d.dollars_saved.point,
    dollars_saved_ci: { lo: d.dollars_saved.lo, hi: d.dollars_saved.hi },
    dollars_per_life: d.cost_per_life_saved_usd,
    misinfo_change: d.misinfo_ratio_change?.point ?? null,
  }))
})

const comparatorArms = computed(() => {
  if (!mcRun.value) return []
  // Include the deltas (treated arms) — baseline has no delta, so showing
  // only treatments is the right framing for "lives saved vs do-nothing".
  return enrichedDeltas.value
})

const cumulativeArms = computed(() => {
  if (!mcRun.value) return []
  const baseline = mcRun.value.baseline
  const arms = [
    {
      intervention_id: 'baseline',
      label: 'Baseline',
      element: 'air',
      cumulative_deaths_mean: cumsum(baseline.deaths_timeline_mean || []),
    },
    ...mcRun.value.interventions.map((o) => ({
      intervention_id: o.intervention_id,
      label: o.label,
      ...visualFor(INTERVENTION_VISUAL, o.intervention_id),
      cumulative_deaths_mean: cumsum(o.deaths_timeline_mean || []),
    })),
  ]
  return arms
})

function cumsum(arr) {
  let acc = 0
  return arr.map((v) => (acc += v))
}

// Hero numbers: pick the SINGLE best intervention by lives saved (not a sum
// across selected interventions). Reasoning: interventions don't combine
// additively — running prebunk + retrofit + evac doesn't add the three
// individual lives_saved values, because each MC arm independently models
// "baseline vs that one intervention." Showing the best single arm is the
// honest framing; a "stacked" hero would overstate value.
const bestDelta = computed(() => {
  if (!enrichedDeltas.value.length) return null
  return [...enrichedDeltas.value].sort(
    (a, b) => b.lives_saved_mean - a.lives_saved_mean,
  )[0]
})
const totalLivesSaved = computed(() => bestDelta.value?.lives_saved_mean ?? 0)
const bestLivesCi = computed(() => bestDelta.value?.lives_saved_ci ?? null)
const totalDollarsSaved = computed(() => bestDelta.value?.dollars_saved_mean ?? 0)
const bestDollarsCi = computed(() => bestDelta.value?.dollars_saved_ci ?? null)

// --- Gating ---
const canRun = computed(
  () => !!selectedScenarioId.value && selectedInterventionIds.value.length > 0,
)

// --- Actions ---
async function loadIndex() {
  try {
    const [s, iv] = await Promise.all([
      auroraApi.listScenarios(),
      auroraApi.listInterventions(),
    ])
    scenarios.value = s.data.scenarios
    interventions.value = iv.data.interventions
  } catch (e) {
    errorMsg.value = `Index fetch failed: ${e.message}`
  }
}

async function onLoadScenario() {
  if (!selectedScenarioId.value) return
  loading.value = true
  errorMsg.value = ''
  try {
    await auroraApi.loadScenario(selectedScenarioId.value, false)
    await loadIndex()
  } catch (e) {
    errorMsg.value = `Load failed: ${e.message}`
  } finally {
    loading.value = false
  }
}

function toggleIntervention(id) {
  const idx = selectedInterventionIds.value.indexOf(id)
  if (idx === -1) selectedInterventionIds.value.push(id)
  else selectedInterventionIds.value.splice(idx, 1)
}

async function onRunMC() {
  if (loading.value || !canRun.value) return
  loading.value = true
  errorMsg.value = ''
  mcRun.value = null
  recentDecisions.value = []
  runState.value = 'running'
  try {
    const resp = await auroraApi.runMCStreaming(selectedScenarioId.value, {
      intervention_ids: selectedInterventionIds.value,
      n_trials: nTrials.value,
      duration_hours: durationHours.value,
      n_population_agents: nPopulation.value,
      use_llm: useLLM.value,
    })
    streamRunId.value = resp.data.run_id
  } catch (e) {
    errorMsg.value = `MC run failed: ${e.message}`
    runState.value = 'idle'
  } finally {
    loading.value = false
  }
}

function onStreamProgress(p) {
  if (p?.recent_decisions) {
    recentDecisions.value = p.recent_decisions
  }
}

async function onStreamDone(result) {
  mcRun.value = result
  runState.value = 'done'
  // Both `mcRun` and `streamRunId` are mutated in the same reactive flush, so
  // Vue swaps the streaming panel for the result section in a single render
  // — no one-frame gap. The panel's polling already stopped before `done`
  // fired (see MCProgressPanel.poll() → stopPolling on done).
  streamRunId.value = null
  await nextTick()
  animateResultReveal()
}

function onStreamError(msg) {
  errorMsg.value = `Streaming MC failed: ${msg}`
  runState.value = 'idle'
  streamRunId.value = null
}

// --- Animation: stagger-in delta cards once result lands ---
function animateResultReveal() {
  if (reduceMotion()) return
  ctx.value?.add(() => {
    if (deltaGrid.value) {
      const cards = deltaGrid.value.querySelectorAll('.delta-card')
      gsap.from(cards, {
        y: 24,
        opacity: 0,
        stagger: 0.08,
        duration: DUR.base,
        ease: EASES.out,
      })
    }
    if (heroRow.value) {
      gsap.from(heroRow.value.children, {
        y: 16,
        opacity: 0,
        stagger: 0.12,
        duration: DUR.base,
        ease: EASES.out,
      })
    }
  })
}

// Auto-reset run state if user changes scenario / interventions after a run.
watch([selectedScenarioId, selectedInterventionIds], () => {
  if (runState.value === 'done') {
    // Keep the result visible but allow a fresh run.
    runState.value = 'idle'
  }
})

onMounted(loadIndex)
</script>

<style scoped>
.aurora {
  --accent: var(--el-aether);
  padding: var(--sp-8) var(--sp-6);
  max-width: 1200px;
  margin: 0 auto;
  color: var(--ink-0);
  background: var(--bg-0);
  min-height: 100vh;
}

.aurora[data-active-element='fire'] { --accent: var(--el-fire); }
.aurora[data-active-element='water'] { --accent: var(--el-water); }
.aurora[data-active-element='earth'] { --accent: var(--el-earth); }
.aurora[data-active-element='air'] { --accent: var(--el-air); }
.aurora[data-active-element='aether'] { --accent: var(--el-aether); }

.hdr {
  margin-bottom: var(--sp-12);
}
.hdr h1 {
  margin: 0 0 var(--sp-2);
  font-size: var(--fz-32);
  font-weight: 700;
  color: var(--ink-0);
  line-height: 1.1;
}
.hdr-sub {
  color: var(--ink-1);
  font-weight: 400;
}
.sub {
  margin: 0;
  color: var(--ink-1);
  font-size: var(--fz-16);
  max-width: 720px;
}

.step {
  margin-bottom: var(--sp-12);
}
.step-head {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  margin-bottom: var(--sp-4);
  padding-bottom: var(--sp-2);
  border-bottom: 1px solid var(--line);
}
.step-num {
  font-size: var(--fz-12);
  font-weight: 600;
  color: var(--accent);
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.1em;
}
.step-head h2 {
  margin: 0;
  font-size: var(--fz-16);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--ink-0);
}
.meta {
  margin-left: auto;
  font-size: var(--fz-12);
  color: var(--ink-2);
  font-variant-numeric: tabular-nums;
}

.muted {
  color: var(--ink-2);
  font-style: italic;
}

.scenario-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--sp-3);
}

.chip-grid {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2);
  margin-bottom: var(--sp-4);
}

.cfg-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-4);
  align-items: end;
  margin-top: var(--sp-3);
  padding-top: var(--sp-3);
  border-top: 1px solid var(--line);
}
.cfg-row label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: var(--fz-12);
  color: var(--ink-2);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: 600;
}
.cfg-row label.ck {
  flex-direction: row;
  align-items: center;
  text-transform: none;
  letter-spacing: normal;
  color: var(--ink-1);
  font-weight: 500;
}
.cfg-row input[type='number'] {
  background: var(--bg-1);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 6px 10px;
  color: var(--ink-0);
  font-size: var(--fz-14);
  width: 90px;
  font-variant-numeric: tabular-nums;
}
.cfg-row input[type='number']:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.step-actions {
  margin-top: var(--sp-4);
}

.btn {
  background: var(--bg-2);
  color: var(--ink-0);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: var(--sp-2) var(--sp-4);
  cursor: pointer;
  font-size: var(--fz-14);
  font-weight: 500;
  transition: border-color 0.15s ease, background 0.15s ease;
}
.btn:hover:not(:disabled) {
  border-color: var(--accent);
}
.btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.btn:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.run-step {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  align-items: flex-start;
}
.err {
  color: var(--el-fire);
  background: color-mix(in srgb, var(--el-fire) 10%, transparent);
  padding: var(--sp-2) var(--sp-3);
  border-radius: 6px;
  font-size: var(--fz-12);
  margin: 0;
}

.streaming-grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
  gap: var(--sp-4);
}
@media (max-width: 920px) {
  .streaming-grid {
    grid-template-columns: 1fr;
  }
}

.hero-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--sp-8);
  margin-bottom: var(--sp-8);
}
@media (max-width: 720px) {
  .hero-row {
    grid-template-columns: 1fr;
    gap: var(--sp-4);
  }
}

.delta-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--sp-3);
  margin-bottom: var(--sp-6);
}

.result-step :deep(.cumulative-chart) {
  margin-top: var(--sp-4);
}

@media (max-width: 720px) {
  .aurora {
    padding: var(--sp-4) var(--sp-3);
  }
  .hdr h1 {
    font-size: var(--fz-24);
  }
}

@media (prefers-reduced-motion: reduce) {
  .btn {
    transition: none;
  }
}
</style>
