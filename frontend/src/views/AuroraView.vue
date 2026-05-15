<!-- SPDX-License-Identifier: Apache-2.0 -->
<template>
  <div class="aurora" :data-active-element="activeElement" :data-current-act="currentAct" ref="root">
    <!-- Acts 0 + 1 are full-bleed brand scenes. Acts 2..5 reuse the legacy
         per-step scaffolding for now; N3-M6' will replace each in turn. -->

    <Act0Brief
      v-if="currentAct === 0"
      :loading="loading"
      @continue="goToAct(1)"
    />

    <Act1CityPick
      v-else-if="currentAct === 1"
      :scenarios="scenarios"
      @back="goToAct(0)"
      @select="onCitySelect"
    />

    <CommandShell v-else ref="shellRef">
      <!-- Topbar: back / title chip / act indicator / START / PAUSE / theme -->
      <template #topbar>
        <button class="topbar-back" @click="goToAct(1)" aria-label="Back to cities">
          <PhArrowLeft :size="14" weight="bold" /> <span>Cities</span>
        </button>
        <div class="topbar-title">
          <span class="word">Aurora</span>
          <span class="div">/</span>
          <span class="city">{{ loadedScenario?.city ?? 'Loading…' }}</span>
          <span v-if="hazardLabel" class="haz" :class="`haz-${hazardElement}`">{{ hazardLabel }}</span>
        </div>
        <div class="topbar-actindex">
          <span class="ai-num">Act {{ currentAct }}</span>
          <span class="ai-of">of 5</span>
        </div>
        <button
          v-if="runState !== 'running'"
          class="topbar-start"
          :disabled="!canRun || loading"
          @click="onRunMC"
        >
          <PhPlay :size="13" weight="fill" />
          <span>{{ mcRun ? 'Re-run' : 'Start simulation' }}</span>
        </button>
        <button
          v-else
          class="topbar-pause"
          @click="onPauseRun"
        >
          <PhPause :size="13" weight="fill" />
          <span>Pause</span>
        </button>
        <button
          class="topbar-theme"
          :aria-label="theme === 'light' ? 'Switch to dark theme' : 'Switch to light theme'"
          @click="toggleTheme"
        >
          <component :is="theme === 'light' ? PhMoon : PhSun" :size="14" weight="duotone" />
        </button>
      </template>

      <!-- Lateral toolbar: briefing pills with click-to-expand inline detail -->
      <template #rail>
        <EventRail :groups="railGroups" />
      </template>

      <!-- Stage: full-bleed map (Act 2/3) — Act 4/5 will dock more here later -->
      <template #stage>
        <div v-if="loadedScenario" class="stage-map">
          <SchematicMap
            :scenario="loadedScenario"
            :basemap-theme="theme"
            :animation-hour="animationHour"
            :mc-run="mcRun"
          />
        </div>
        <div v-else class="stage-loading">
          <div class="loading-pulse"></div>
          <span>Building scenario…</span>
        </div>
      </template>

      <!-- Right-side EVENTS panel — always visible. Three states keyed
           on runState: idle (briefing), running (live MC + agent feed),
           done (Result hero + Gemma proposals). -->
      <template #events>
        <div class="events-panel" :data-state="runState">

          <!-- IDLE: nothing has run yet -->
          <div v-if="runState === 'idle' && !mcRun" class="events-idle">
            <div class="events-header">
              <PhInfo :size="14" weight="duotone" color="var(--el-aether)" />
              <span>Briefing</span>
            </div>
            <p class="events-blurb">
              Pick a hazard scenario from the rail. Hit
              <strong>Start simulation</strong> in the topbar to run the
              Monte Carlo against {{ nPopulation }} archetype agents over
              {{ durationHours }} hours.
            </p>
            <div class="events-meta">
              <div><PhBuildings :size="12" weight="duotone" color="var(--el-water)" /> {{ loadedScenario?.buildings?.length ?? 0 }} buildings</div>
              <div><PhFirstAidKit :size="12" weight="duotone" color="var(--el-water)" /> {{ (loadedScenario?.hospitals?.length ?? 0) + (loadedScenario?.fire_stations?.length ?? 0) + (loadedScenario?.shelters?.length ?? 0) }} responders</div>
              <div><PhUsersThree :size="12" weight="duotone" color="var(--el-aether)" /> {{ nPopulation }} agents · 9 archetypes</div>
              <div><PhCpu :size="12" weight="duotone" color="var(--el-aether)" /> Gemma 4 e4b · cached</div>
            </div>
            <div class="events-cfg">
              <label><span>Trials</span><input type="number" v-model.number="nTrials" min="1" max="64" /></label>
              <label><span>Population</span><input type="number" v-model.number="nPopulation" min="20" max="500" /></label>
              <label><span>Hours</span><input type="number" v-model.number="durationHours" min="6" max="72" /></label>
            </div>
            <p class="events-cite">
              <PhCpu :size="11" weight="duotone" color="var(--el-aether)" />
              &nbsp;Methodology: HAZUS-MH 2.1 fragility · Omori–Utsu aftershock · Gemma 4 reasoning over archetypes per district per phase
            </p>
          </div>

          <!-- RUNNING: progress bars + agent feed -->
          <div v-if="runState === 'running'" class="events-running">
            <div class="events-header">
              <PhRadio :size="14" weight="duotone" color="var(--el-fire)" />
              <span>Live · Disaster unfolding</span>
            </div>
            <MCProgressPanel
              v-if="streamRunId"
              :run-id="streamRunId"
              :scenario-id="selectedScenarioId"
              :arms="streamingArms"
              @done="onStreamDone"
              @progress="onStreamProgress"
              @error="onStreamError"
            />
            <div class="events-feed">
              <div class="feed-label">Agent decision feed</div>
              <AgentLogTicker :decisions="recentDecisions" :max-visible="8" />
            </div>
          </div>

          <!-- DONE: hero result + Gemma proposals -->
          <div v-if="runState === 'done' && mcRun" class="events-done">
            <div class="events-header">
              <PhChartLineUp :size="14" weight="duotone" color="var(--el-aether)" />
              <span>Outcome · {{ mcRun.n_trials }} trials · {{ mcRun.duration_hours }}h</span>
            </div>
            <div class="result-hero">
              <div class="hero-stat">
                <div class="hero-num">{{ Math.round(totalLivesSaved).toLocaleString() }}</div>
                <div class="hero-label">Lives saved</div>
                <div v-if="bestLivesCi" class="hero-ci">CI {{ Math.round(bestLivesCi.lo).toLocaleString() }}–{{ Math.round(bestLivesCi.hi).toLocaleString() }}</div>
              </div>
              <div class="hero-stat">
                <div class="hero-num">${{ formatCurrency(totalDollarsSaved) }}</div>
                <div class="hero-label">Dollars saved</div>
              </div>
            </div>
            <div v-if="bestDelta" class="best-intervention">
              <div class="bi-label">Best intervention</div>
              <div class="bi-name">{{ bestDelta.label || bestDelta.intervention_id }}</div>
              <div v-if="bestDelta.dollars_per_life" class="bi-cost">
                ${{ formatCurrency(bestDelta.dollars_per_life) }} per life saved
              </div>
            </div>
            <div v-if="enrichedDeltas.length > 1" class="all-deltas">
              <div class="all-deltas-title">All interventions</div>
              <div v-for="d in enrichedDeltas" :key="d.intervention_id" class="delta-row">
                <span class="dr-name">{{ d.label || d.intervention_id }}</span>
                <span class="dr-lives">{{ Math.round(d.lives_saved_mean).toLocaleString() }}</span>
              </div>
            </div>

            <!-- Gemma 4 prevention proposals -->
            <div class="proposals">
              <div class="proposals-title">
                <PhSparkle :size="12" weight="fill" color="var(--el-aether)" />
                <span>Gemma 4 prevention proposals</span>
                <span v-if="proposingNow" class="proposals-status">analyzing…</span>
              </div>
              <div v-if="proposingNow" class="proposals-loading">
                Gemma 4 e4b is reading the report and selecting prevention measures…
              </div>
              <div v-else-if="proposedInterventions?.proposals?.length">
                <div v-for="p in proposedInterventions.proposals"
                     :key="p.intervention_id"
                     class="proposal-card">
                  <div class="prop-row">
                    <span class="prop-name">{{ p.label }}</span>
                    <span class="prop-cost">${{ formatCurrency(p.cost_usd) }}</span>
                  </div>
                  <div class="prop-rationale">{{ p.rationale }}</div>
                </div>
                <p v-if="proposedInterventions.summary" class="proposals-summary">
                  {{ proposedInterventions.summary }}
                </p>
              </div>
              <div v-else class="proposals-empty">
                Gemma did not return proposals (fallback ranking shown).
              </div>
            </div>

            <p class="events-cite">
              <PhCpu :size="11" weight="duotone" color="var(--el-aether)" />
              &nbsp;Monte Carlo · 90% CI · HAZUS-MH 2.1 · Gemma 4 e4b
            </p>
          </div>

          <!-- ERROR overlay (any state) -->
          <div v-if="errorMsg" class="events-error">
            <PhWarning :size="14" weight="bold" color="var(--el-fire)" />
            <span>{{ errorMsg }}</span>
            <button v-if="ollamaError && useLLM" class="retry-btn" @click="retryWithoutLLM">
              Try without Gemma 4
            </button>
          </div>
        </div>
      </template>
    </CommandShell>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, shallowReactive, watch } from 'vue'
import {
  PhArrowLeft,
  PhBuildings,
  PhChartLineUp,
  PhCpu,
  PhFirstAidKit,
  PhInfo,
  PhMoon,
  PhPause,
  PhPlay,
  PhRadio,
  PhSparkle,
  PhSun,
  PhUsersThree,
  PhWarning,
  PhWaveSawtooth,
} from '@phosphor-icons/vue'
import { auroraApi } from '../api/aurora.js'
import { useGsap } from '@/design/useGsap'
import { DUR, EASES } from '@/design/motion'
import CommandShell from '@/components/aurora/CommandShell.vue'
import EventRail from '@/components/aurora/EventRail.vue'
import ScenarioCard from '@/components/aurora/ScenarioCard.vue'
import InterventionChip from '@/components/aurora/InterventionChip.vue'
import RunButton from '@/components/aurora/RunButton.vue'
import SkeletonCard from '@/components/aurora/SkeletonCard.vue'
import MCProgressPanel from '@/components/aurora/MCProgressPanel.vue'
import AgentLogTicker from '@/components/aurora/AgentLogTicker.vue'
import HeroNumber from '@/components/aurora/HeroNumber.vue'
import DeltaCard from '@/components/aurora/DeltaCard.vue'
import ComparatorTable from '@/components/aurora/ComparatorTable.vue'
import CumulativeChart from '@/components/aurora/CumulativeChart.vue'
import SchematicMap from '@/components/aurora/SchematicMap.vue'
import Act0Brief from '@/components/aurora/acts/Act0Brief.vue'
import Act1CityPick from '@/components/aurora/acts/Act1CityPick.vue'

const root = ref(null)
// Current act in the Prevention Lab story.
//   0 = brand intro
//   1 = city pick
//   2 = topology + reference scenarios on the map
//   3 = briefing room (legacy interventions panel until N4 lands)
//   4 = live sim
//   5 = Prevention Lab — re-run + compare
// M7' will URL-bind this via ?act=N. For now it lives only in memory.
const currentAct = ref(0)

// Shell ref (no drawer state; drawer system was removed in the
// events-panel redesign, but shellRef is still kept for future use).
const shellRef = ref(null)

// Per-scenario map replay timers. Each entry is
//   { intervalId, runId }
// keyed by scenario_id. This replaces the singleton _replayTimer so a
// timer that started under one scenario can be cancelled or self-clear
// when the user navigates to a different city (F1 — cross-city replay
// leak). onPauseRun and startMapReplay both go through this Map.
const _replayTimers = new Map()

// H4: theme — light by default per civic-tech convention; dark optional
// for night-ops / low-light demos. Persists in localStorage and reflects
// onto :root[data-theme] which the tokens.css cascade reads.
const theme = ref(loadInitialTheme())

function loadInitialTheme() {
  if (typeof window === 'undefined') return 'light'
  const stored = window.localStorage?.getItem('aurora-theme')
  if (stored === 'light' || stored === 'dark') return stored
  return 'light'
}

function applyTheme(t) {
  if (typeof document === 'undefined') return
  document.documentElement.setAttribute('data-theme', t)
}

function toggleTheme() {
  theme.value = theme.value === 'light' ? 'dark' : 'light'
  applyTheme(theme.value)
  try { window.localStorage?.setItem('aurora-theme', theme.value) } catch {}
}
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
const loading = ref(false)
const errorMsg = ref('')

// Phase 1 — Per-scenario state preservation.
// Every Monte Carlo run, intervention selection, animation step, and
// loaded scenario blob lives in its OWN entry inside `scenarioStates`,
// keyed by scenario_id. Switching cities just changes which entry the
// computed getters below read from — prior runs stay intact. The map
// is `shallowReactive` so MC payload arrays (huge per-trial timelines)
// don't trigger deep proxy traversal every SchematicMap re-render.
const scenarioStates = shallowReactive({})

// `?gemma=full` URL flag sets this; new scenarios created later inherit
// it as their default useLLM. Existing scenarios already in the map get
// the flag retroactively when applyActFromUrl parses it.
const _globalUseLLM = ref(false)

function initScenarioState(id) {
  if (!id) return
  // Cap at 6 entries to bound memory across long demo sessions.
  if (Object.keys(scenarioStates).length >= 6 && !scenarioStates[id]) {
    console.warn('Aurora: scenarioStates at cap (6); cannot init', id)
    return
  }
  if (scenarioStates[id]) return
  scenarioStates[id] = {
    mcRun: null,
    streamRunId: null,
    runState: 'idle',
    recentDecisions: [],
    selectedInterventionIds: [],
    proposedInterventions: null,
    animationHour: 0,
    nTrials: 8,
    nPopulation: 80,
    durationHours: 24,
    lastRunAt: null,
    useLLM: _globalUseLLM.value,
    loadedScenario: null,
    // Reserved for Phase 2b — keep []
    mcRunHistory: [],
  }
}

function setForCurrent(field, value) {
  const id = selectedScenarioId.value
  if (!id) return
  if (!scenarioStates[id]) initScenarioState(id)
  // Guard against the cap-refused case.
  if (!scenarioStates[id]) return
  scenarioStates[id][field] = value
}

// Eagerly seed the default scenario so first-paint reads return defaults
// instead of `undefined`.
initScenarioState(selectedScenarioId.value)

// --- Per-scenario computed getters ----------------------------------------
// Reads go through scenarioStates[selectedScenarioId.value]. For getters
// that the template writes back via .value = X (mcRun/runState/...), we
// use writable computeds that mutate the current scenario's entry. For
// v-model.number bindings (nTrials/nPopulation/durationHours) we also
// need writable computeds so the input change updates per-scenario state.
//
// For selectedInterventionIds: returning the underlying array reference
// is fine because the array lives inside a shallowReactive — push/splice
// on it triggers the parent re-render via the shallowReactive proxy.
function _cur() {
  const id = selectedScenarioId.value
  return id ? scenarioStates[id] : null
}

const mcRun = computed({
  get: () => _cur()?.mcRun ?? null,
  set: (v) => setForCurrent('mcRun', v),
})
const streamRunId = computed({
  get: () => _cur()?.streamRunId ?? null,
  set: (v) => setForCurrent('streamRunId', v),
})
const runState = computed({
  get: () => _cur()?.runState ?? 'idle',
  set: (v) => setForCurrent('runState', v),
})
const recentDecisions = computed({
  get: () => _cur()?.recentDecisions ?? [],
  set: (v) => setForCurrent('recentDecisions', v),
})
const selectedInterventionIds = computed({
  get: () => _cur()?.selectedInterventionIds ?? [],
  set: (v) => setForCurrent('selectedInterventionIds', v),
})
const proposedInterventions = computed({
  get: () => _cur()?.proposedInterventions ?? null,
  set: (v) => setForCurrent('proposedInterventions', v),
})
const loadedScenario = computed({
  get: () => _cur()?.loadedScenario ?? null,
  set: (v) => setForCurrent('loadedScenario', v),
})
const animationHour = computed({
  get: () => _cur()?.animationHour ?? 0,
  set: (v) => setForCurrent('animationHour', v),
})
const nTrials = computed({
  get: () => _cur()?.nTrials ?? 8,
  set: (v) => setForCurrent('nTrials', v),
})
const nPopulation = computed({
  get: () => _cur()?.nPopulation ?? 80,
  set: (v) => setForCurrent('nPopulation', v),
})
const durationHours = computed({
  get: () => _cur()?.durationHours ?? 24,
  set: (v) => setForCurrent('durationHours', v),
})
// useLLM falls back to the URL-flagged default for scenarios that haven't
// been initialised yet (computed getters can be hit before init for
// brand-new ids). Once an entry exists, its own value wins.
const useLLM = computed({
  get: () => {
    const cur = _cur()
    return cur ? cur.useLLM : _globalUseLLM.value
  },
  set: (v) => setForCurrent('useLLM', v),
})

// === PHASE 2B INSERTS COMPUTEDS HERE ===
// e.g. currentAct, mcRunHistory views, etc.

// Detect Ollama-not-running so we can offer the "Try without Gemma 4" path.
const ollamaError = computed(() => {
  if (!errorMsg.value) return false
  const m = errorMsg.value.toLowerCase()
  return (
    m.includes('ollama') ||
    m.includes('connection refused') ||
    m.includes('econnrefused') ||
    m.includes('no llm client') ||
    m.includes('no such model')
  )
})

async function retryWithoutLLM() {
  useLLM.value = false
  errorMsg.value = ''
  await onRunMC()
}

// --- Element / icon enrichment for the new visual layer ---
// Disasters → element + Phosphor icon
const SCENARIO_VISUAL = {
  // Real, data-anchored scenarios
  'la-puente-hills-m72-ref':  { element: 'earth', icon: 'Mountains' },
  'valencia-dana-2024':       { element: 'water', icon: 'WaveTriangle' },
  'pompeii-79':               { element: 'fire',  icon: 'Flame' },
  'joplin-ef5-2011':          { element: 'air',   icon: 'Wind' },
  'turkey-syria-m78-2023':    { element: 'aether', icon: 'Users' },
  // Mythological showcase
  'atlantis':                 { element: 'water', icon: 'WaveTriangle' },
}

const INTERVENTION_VISUAL = {
  baseline: { element: 'air', icon: 'Siren' },
  // LA Puente Hills M7.2 interventions
  preposition_d03_4amb: { element: 'aether', icon: 'FirstAidKit' },
  evac_d03_30min_early: { element: 'earth', icon: 'ClockClockwise' },
  retrofit_d03_w1: { element: 'earth', icon: 'Buildings' },
  retrofit_d02_c1l: { element: 'earth', icon: 'Buildings' },
  prebunk_misinfo: { element: 'aether', icon: 'ChatCircleDots' },
  fire_break_d03: { element: 'fire', icon: 'Flame' },
  // Valencia DANA 2024 interventions
  vlc_evac_es_alert_4h_early: { element: 'water', icon: 'ClockClockwise' },
  vlc_preposition_ume_torrent: { element: 'aether', icon: 'FirstAidKit' },
  vlc_retrofit_ground_floors: { element: 'water', icon: 'Buildings' },
  vlc_prebunk_dana_misinfo: { element: 'aether', icon: 'ChatCircleDots' },
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

// Hazard chip in the topbar (Acts 2..5)
const HAZARD_ELEMENT = {
  earthquake: 'earth',
  flood: 'water',
  volcanic: 'fire',
  tornado: 'air',
}
const hazardElement = computed(
  () => HAZARD_ELEMENT[loadedScenario.value?.hazard?.kind] ?? 'aether',
)
const hazardLabel = computed(() => {
  const h = loadedScenario.value?.hazard
  if (!h) return null
  const kind = (h.kind ?? '').replace(/_/g, ' ')
  const mag = h.magnitude ? ` M${h.magnitude}` : ''
  return `${kind}${mag}`.trim().toUpperCase()
})

// Lateral rail groups — each pill is one click-to-reveal section. Stats
// pull from the loadedScenario when present so judges see real numbers
// the moment they pick a city.
// Compact $-formatter for hero numbers + cost-per-life. 1.4M / 690K shape.
function formatCurrency(n) {
  if (n == null || !isFinite(n)) return '—'
  const abs = Math.abs(n)
  if (abs >= 1e9) return (n / 1e9).toFixed(1) + 'B'
  if (abs >= 1e6) return (n / 1e6).toFixed(1) + 'M'
  if (abs >= 1e3) return (n / 1e3).toFixed(0) + 'K'
  return Math.round(n).toLocaleString()
}

const railGroups = computed(() => {
  const s = loadedScenario.value
  const h = s?.hazard
  const respondersTotal =
    (s?.hospitals?.length ?? 0) +
    (s?.fire_stations?.length ?? 0) +
    (s?.shelters?.length ?? 0)
  // Each pill: stat (always visible) + detail (shown when expanded inline).
  return [
    {
      id: 'hazard',
      label: 'Hazard',
      stat: hazardLabel.value ?? 'Loading…',
      element: hazardElement.value,
      icon: 'WaveSawtooth',
      detail: h ? [
        { key: 'Kind', val: h.kind ?? '—' },
        ...(h.magnitude ? [{ key: 'Magnitude', val: `M${h.magnitude}` }] : []),
        ...(h.depth_km != null ? [{ key: 'Depth', val: `${h.depth_km} km` }] : []),
        { key: 'Duration', val: `${h.duration_hours ?? '—'} h` },
        { key: 'Districts', val: s?.districts?.length ?? 0 },
      ] : null,
      cite: 'HAZUS-MH 2.1 fragility · Omori–Utsu aftershock chain',
    },
    {
      id: 'population',
      label: 'Population',
      stat: `${nPopulation.value} agents · 9 archetypes`,
      element: 'aether',
      icon: 'UsersThree',
      detail: [
        { key: 'Agents', val: nPopulation.value },
        { key: 'Archetypes', val: 9 },
        { key: 'Trials', val: nTrials.value },
        { key: 'Hours', val: durationHours.value },
      ],
      cite: 'Gemma 4 e2b reasons over each archetype × district × phase. Cached across trials.',
    },
    {
      id: 'responders',
      label: 'Responders',
      stat: `${respondersTotal} units`,
      element: 'water',
      icon: 'FirstAidKit',
      detail: [
        { key: 'Hospitals', val: s?.hospitals?.length ?? 0 },
        { key: 'Fire stations', val: s?.fire_stations?.length ?? 0 },
        { key: 'Shelters', val: s?.shelters?.length ?? 0 },
      ],
    },
  ]
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
// Baseline runs as soon as a scenario is loaded. Interventions arrive
// post-run from Gemma's report analysis (M6' Prevention Lab); their
// selection re-runs additional MC arms in place.
const canRun = computed(() => !!selectedScenarioId.value)

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
  const targetId = selectedScenarioId.value
  if (!targetId) return
  if (!scenarioStates[targetId]) initScenarioState(targetId)
  loading.value = true
  errorMsg.value = ''
  try {
    // M2.1: Use /preview (pure in-memory scenario build, no Neo4j) to
    // populate the schematic map. The legacy /load route is Neo4j-backed
    // for graph-tools persistence — not needed for the map. Decoupling
    // means the demo runs even when Docker / Neo4j aren't up.
    const resp = await auroraApi.previewScenario(targetId)
    // resp is the {success, data} envelope; resp.data is the scenario.
    // Write to the captured target id's entry (not the now-current one)
    // so mid-flight scenario switches don't cross-write.
    if (resp?.data && scenarioStates[targetId]) {
      scenarioStates[targetId].loadedScenario = resp.data
    }
    await loadIndex()
  } catch (e) {
    errorMsg.value = `Load failed: ${e.message}`
  } finally {
    loading.value = false
  }
}

// M2.1: auto-preview on scenario selection — no need for a "Refresh DB"
// click. The map appears as soon as the user picks a scenario. Phase 1
// adds a per-scenario init + a "skip if already loaded" guard so flipping
// back to a city the user already visited is instant.
watch(selectedScenarioId, async (newId) => {
  if (!newId) return
  if (!scenarioStates[newId]) initScenarioState(newId)
  if (!scenarioStates[newId]?.loadedScenario) {
    await onLoadScenario()
  }
})

function toggleIntervention(id) {
  // selectedInterventionIds is a computed that returns the underlying
  // array reference from scenarioStates[currentId]. Push/splice mutate
  // in place — shallowReactive propagates the change.
  const list = selectedInterventionIds.value
  const idx = list.indexOf(id)
  if (idx === -1) list.push(id)
  else list.splice(idx, 1)
}

// === PHASE 2B INSERTS HERE === (e.g. toggleProposal — keep adjacent to
// toggleIntervention so the two click paths stay together.)

async function onRunMC() {
  if (loading.value || !canRun.value) return
  // === PHASE 2B INSERTS HERE ===
  // AbortController per-scenario setup + mcRunHistory.push() before
  // the existing reset lines below.
  loading.value = true
  errorMsg.value = ''
  mcRun.value = null
  proposedInterventions.value = null
  recentDecisions.value = []
  runState.value = 'running'
  // Events panel auto-shows the running state via runState reactivity.
  try {
    const resp = await auroraApi.runMCStreaming(selectedScenarioId.value, {
      intervention_ids: selectedInterventionIds.value,
      n_trials: nTrials.value,
      duration_hours: durationHours.value,
      n_population_agents: nPopulation.value,
      use_llm: useLLM.value,
    })
    streamRunId.value = resp.data.run_id
    // From here MCProgressPanel polls /progress and emits `progress`/`done`.
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
  streamRunId.value = null
  await nextTick()
  // Start the on-map disaster replay (per-hour district color animation).
  startMapReplay()
  // Events panel auto-swaps to 'done' state via runState reactivity.
  // Fire Gemma proposals in the background (3-15s on cold cache).
  fetchProposals(result)
}

/**
 * onPauseRun — stop the local map replay AND cancel any in-flight
 * progress poller. The backend MC keeps running (typical case: it's
 * already finished from cache anyway), but the user sees the UI
 * stop animating and the events panel goes back to idle.
 *
 * Phase 1: only clears the timer for the CURRENT scenario so pausing
 * in city A doesn't kill an animation that was already running in
 * city B (or that the user paused-then-navigated-back-to).
 */
function onPauseRun() {
  const id = selectedScenarioId.value
  const t = _replayTimers.get(id)
  if (t) {
    clearInterval(t.intervalId)
    _replayTimers.delete(id)
  }
  // Mark the run as done if we have data, otherwise reset to idle.
  if (mcRun.value) {
    runState.value = 'done'
  } else {
    runState.value = 'idle'
    streamRunId.value = null
  }
}

// --- Map replay: animate `animationHour` from 0..duration_hours over
// ~12 wall-seconds so the SchematicMap can render per-hour district
// damage progression. Reads from the baseline timeline. Each interval
// is tagged with the scenario_id and the streamRunId that started it,
// so a tick fires on a city the user has since navigated away from
// (or that another run started under) will self-clear.
function startMapReplay() {
  const id = selectedScenarioId.value
  if (!id) return
  if (!scenarioStates[id]) initScenarioState(id)
  // The token: prefer the in-flight streamRunId; fall back to a synthetic
  // `done-…` token when the run already completed and we're just animating.
  const runToken = scenarioStates[id]?.streamRunId ?? `done-${Date.now()}`
  // Cancel any prior timer on this scenario before starting a new one.
  const prior = _replayTimers.get(id)
  if (prior) clearInterval(prior.intervalId)

  const dur = mcRun.value?.duration_hours ?? 24
  const wallSecondsTotal = 12 // ~half the v3-plan target; tight & legible
  const tick = (wallSecondsTotal * 1000) / dur
  let h = 0
  if (scenarioStates[id]) scenarioStates[id].animationHour = 0

  const intervalId = setInterval(() => {
    const cur = scenarioStates[id]
    // Self-clear if the entry vanished or another run took over.
    if (!cur || (cur.streamRunId !== runToken && !runToken.startsWith('done-'))) {
      clearInterval(intervalId)
      _replayTimers.delete(id)
      return
    }
    h += 1
    cur.animationHour = h
    if (h >= dur) {
      clearInterval(intervalId)
      _replayTimers.delete(id)
    }
  }, tick)
  _replayTimers.set(id, { intervalId, runId: runToken })
}

// --- Gemma intervention proposals (fired on done) ---
const proposingNow = ref(false)
async function fetchProposals(result) {
  if (!result?.baseline) return
  const targetId = selectedScenarioId.value
  if (!targetId) return
  if (!scenarioStates[targetId]) initScenarioState(targetId)
  proposingNow.value = true
  try {
    const baseline = {
      deaths: Math.round(result.baseline.deaths?.point ?? 0),
      injuries: Math.round(result.baseline.injuries?.point ?? 0),
      economic_loss_usd: Math.round(result.baseline.economic_loss_usd?.point ?? 0),
      duration_hours: result.duration_hours ?? 24,
      // The frontend doesn't have per-district from the response envelope,
      // so leave it empty — the backend handles missing district data.
      deaths_by_district: {},
    }
    const resp = await auroraApi.proposeInterventions(targetId, baseline, 4)
    // Write back to the captured target scenario — the user may have
    // navigated away while Gemma was thinking.
    if (scenarioStates[targetId]) {
      scenarioStates[targetId].proposedInterventions = resp.data
    }
  } catch (e) {
    // Non-fatal — Result drawer just doesn't show proposals.
    console.warn('proposeInterventions failed', e)
    if (scenarioStates[targetId]) {
      scenarioStates[targetId].proposedInterventions = {
        proposals: [], summary: '', model: 'unavailable',
      }
    }
  } finally {
    proposingNow.value = false
  }
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

// Phase 1: the previous `watch([selectedScenarioId, selectedInterventionIds])`
// that forced runState back to 'idle' on any change is no longer needed —
// each scenario carries its own runState in scenarioStates, so switching
// cities naturally reveals whatever state THAT city last had.
//
// (M2.1 collapsed: the auto-preview watch above replaces both the
// stale-clear and the explicit "Refresh DB" click. Picking a scenario
// = loading its preview into the map immediately.)

async function applyDemoSeed() {
  // ?seed=demo runs the baseline straight through; interventions are
  // proposed by Gemma post-run (no longer pre-selected).
  if (typeof window === 'undefined') return
  const params = new URLSearchParams(window.location.search)
  if (params.get('seed') !== 'demo') return
  const id = 'la-puente-hills-m72-ref'
  if (!scenarioStates[id]) initScenarioState(id)
  // Demo-tuned MC params for the seeded scenario.
  if (scenarioStates[id]) {
    scenarioStates[id].selectedInterventionIds = []
    scenarioStates[id].nTrials = 20
    scenarioStates[id].nPopulation = 80
    scenarioStates[id].durationHours = 24
  }
  selectedScenarioId.value = id
  currentAct.value = 2  // demo skips brand + city pick
  await loadIndex()
  // Force the preview explicitly — if `id` was already the default,
  // assigning it to selectedScenarioId.value is a no-op for the watch.
  await onLoadScenario()
  setTimeout(() => {
    if (canRun.value && runState.value === 'idle') onRunMC()
  }, 1000)
}

// --- Act navigation ---
function goToAct(n) {
  currentAct.value = n
  if (typeof window !== 'undefined') {
    // Best effort: scroll to top so users don't land mid-page after a jump.
    window.scrollTo({ top: 0, behavior: 'instant' })
  }
}

async function onCitySelect(scenarioId) {
  // If the user clicks the city that's already selected (Vue defaults
  // selectedScenarioId to 'la-puente-hills-m72-ref'), the watcher
  // skips because newId === oldId. Always advance the act AND fire
  // onLoadScenario explicitly so the map renders either way.
  const isSameCity = selectedScenarioId.value === scenarioId
  selectedScenarioId.value = scenarioId
  goToAct(2)
  if (isSameCity) {
    await onLoadScenario()
  }
  // else: the watch(selectedScenarioId, …) handler will run onLoadScenario
}

// Sub-headline for Acts 2..5 — adapts to the selected hazard so judges see
// the calibrated unit on the page chrome from Act 2 onward.
const heroSub = computed(() => {
  const h = loadedScenario.value?.hazard
  if (!h) {
    return 'A/B-test civic decisions before they cost anyone.'
  }
  const kind = (h.kind ?? '').replace(/_/g, ' ')
  const mag = h.magnitude ? ` · M${h.magnitude}` : ''
  return `Reference scenario · ${kind}${mag} · Gemma 4 reasons over archetypes per district per phase.`
})

// Lock body scroll when in Acts 2..5 (CommandShell owns the viewport).
// Acts 0/1 keep normal scroll behavior in case future copy needs it.
watch(currentAct, (n) => {
  if (typeof document === 'undefined') return
  const shellMode = n >= 2 && n <= 5
  document.body.style.overflow = shellMode ? 'hidden' : ''
}, { immediate: false })

// Apply ?act=N from URL on cold load (precursor to M7' full URL driver).
// `?gemma=full` opts into per-cell Gemma decisions inside MC trials (slow);
// `?gemma=off` is the emergency fallback when Ollama is down at demo time.
function applyActFromUrl() {
  if (typeof window === 'undefined') return
  const params = new URLSearchParams(window.location.search)
  const a = parseInt(params.get('act') ?? '', 10)
  if (Number.isFinite(a) && a >= 0 && a <= 5) {
    currentAct.value = a
  }
  // ?gemma flag flips _globalUseLLM (the default for any future entries
  // initialised by initScenarioState) AND propagates onto every existing
  // entry so the user immediately sees the change everywhere they've
  // already been.
  const gem = params.get('gemma')
  if (gem === 'full' || gem === 'off') {
    const v = gem === 'full'
    _globalUseLLM.value = v
    for (const k of Object.keys(scenarioStates)) {
      scenarioStates[k].useLLM = v
    }
  }
}

onMounted(async () => {
  applyTheme(theme.value)
  applyActFromUrl()
  // Apply scroll lock for the (possibly URL-restored) initial act.
  if (typeof document !== 'undefined' && currentAct.value >= 2) {
    document.body.style.overflow = 'hidden'
  }
  await loadIndex()
  await applyDemoSeed()
  // If the URL deep-linked to act 2..5 but the user never went through
  // Act 1 (where the watcher fires onLoadScenario), the map will be
  // stuck on "BUILDING SCENARIO…". Force-load the default scenario.
  if (currentAct.value >= 2 && !loadedScenario.value && selectedScenarioId.value) {
    await onLoadScenario()
  }
})
</script>

<style scoped>
.aurora {
  --accent: var(--el-aether);
  color: var(--ink-0);
  background: var(--bg-0);
  min-height: 100vh;
}

/* Acts 2..5 are owned by CommandShell which is position:fixed inset:0;
   the .aurora wrapper is a passthrough so the shell can size to viewport. */
.aurora[data-current-act='2'],
.aurora[data-current-act='3'],
.aurora[data-current-act='4'],
.aurora[data-current-act='5'] {
  padding: 0;
  max-width: none;
  margin: 0;
}

/* Acts 0+1 are full-bleed brand canvases — no chrome padding. */
.aurora[data-current-act='0'],
.aurora[data-current-act='1'] {
  padding: 0;
  max-width: 100%;
  margin: 0;
}

/* Back-to-cities button (Acts 2..5) */
.back {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: transparent;
  border: 1px solid var(--line);
  color: var(--ink-1);
  padding: 4px 10px;
  border-radius: 6px;
  font-family: var(--ff-mono);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  cursor: pointer;
  margin-bottom: var(--sp-3);
}
.back:hover { color: var(--ink-0); border-color: var(--ink-2); }

.aurora[data-active-element='fire'] { --accent: var(--el-fire); }
.aurora[data-active-element='water'] { --accent: var(--el-water); }
.aurora[data-active-element='earth'] { --accent: var(--el-earth); }
.aurora[data-active-element='air'] { --accent: var(--el-air); }
.aurora[data-active-element='aether'] { --accent: var(--el-aether); }

/* ---- Topbar (Acts 2..5) ---- */
.topbar-back {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  background: transparent;
  border: 1px solid var(--line);
  color: var(--ink-1);
  padding: 5px 10px;
  border-radius: 6px;
  font-family: var(--ff-mono);
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  cursor: pointer;
}
.topbar-back:hover { color: var(--ink-0); border-color: var(--ink-2); }

.topbar-title {
  flex: 1;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--ink-1);
}
.topbar-title .word { font-weight: 700; color: var(--ink-0); }
.topbar-title .div { color: var(--ink-2); }
.topbar-title .city { font-weight: 500; color: var(--ink-0); }
.topbar-title .haz {
  display: inline-flex;
  align-items: center;
  padding: 3px 8px;
  border-radius: 999px;
  font-family: var(--ff-mono);
  font-size: 10px;
  letter-spacing: 0.08em;
  border: 1px solid var(--line);
  background: var(--bg-2);
  color: var(--ink-1);
  margin-left: 6px;
}
.haz-earth  { border-color: var(--el-earth); color: var(--el-earth); }
.haz-water  { border-color: var(--el-water); color: var(--el-water); }
.haz-fire   { border-color: var(--el-fire);  color: var(--el-fire); }
.haz-air    { border-color: var(--el-air);   color: var(--el-air); }
.haz-aether { border-color: var(--el-aether);color: var(--el-aether); }

.topbar-actindex {
  display: inline-flex;
  align-items: baseline;
  gap: 5px;
  font-family: var(--ff-mono);
  font-size: 11px;
  letter-spacing: 0.08em;
  color: var(--ink-2);
  text-transform: uppercase;
  margin-right: var(--sp-3);
}
.topbar-actindex .ai-num { color: var(--ink-0); font-weight: 600; }

/* Topbar primary action: START (green = go) and PAUSE (amber = pause) */
.topbar-start, .topbar-pause {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border-radius: 8px;
  border: none;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease, opacity 0.15s ease;
  font-variant-numeric: tabular-nums;
}
.topbar-start {
  background: var(--el-air);
  color: var(--bg-0);
  box-shadow: 0 0 0 1px rgba(138, 201, 38, 0.35), 0 4px 14px -6px rgba(138, 201, 38, 0.55);
}
.topbar-start:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 0 0 1px rgba(138, 201, 38, 0.5), 0 8px 20px -6px rgba(138, 201, 38, 0.65);
}
.topbar-start:disabled { opacity: 0.4; cursor: not-allowed; box-shadow: none; }

.topbar-pause {
  background: var(--el-earth);  /* yellow = caution / pause */
  color: var(--bg-0);
  box-shadow: 0 0 0 1px rgba(255, 202, 58, 0.35), 0 4px 14px -6px rgba(255, 202, 58, 0.5);
}
.topbar-pause:hover {
  transform: translateY(-1px);
  box-shadow: 0 0 0 1px rgba(255, 202, 58, 0.5), 0 8px 20px -6px rgba(255, 202, 58, 0.65);
}

.topbar-theme {
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: 1px solid var(--line);
  border-radius: 6px;
  color: var(--ink-1);
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}
.topbar-theme:hover {
  background: var(--bg-2);
  border-color: var(--ink-2);
  color: var(--ink-0);
}
.topbar-theme:focus-visible { outline: 2px solid var(--el-aether); outline-offset: 2px; }

/* ---- Right-side EVENTS panel ---- */
.events-panel {
  padding: 14px var(--sp-3) var(--sp-3);
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  min-height: 100%;
  position: relative;
}
.events-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: var(--ff-mono);
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--ink-2);
  padding-bottom: var(--sp-2);
  border-bottom: 1px solid var(--line);
}
.events-blurb {
  margin: 0;
  font-size: 12px;
  color: var(--ink-1);
  line-height: 1.55;
}
.events-blurb strong { color: var(--ink-0); font-weight: 600; }
.events-meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: var(--sp-3);
  background: var(--bg-2);
  border: 1px solid var(--line);
  border-radius: 8px;
  font-family: var(--ff-mono);
  font-size: 11px;
  color: var(--ink-1);
}
.events-meta > div {
  display: flex;
  align-items: center;
  gap: 8px;
}
.events-cfg {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.events-cfg label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-family: var(--ff-mono);
  font-size: 10px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--ink-2);
  gap: 8px;
}
.events-cfg input[type='number'] {
  width: 70px;
  background: var(--bg-2);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 4px 8px;
  color: var(--ink-0);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}
.events-cite {
  margin: auto 0 0;  /* push to bottom of flex column */
  padding-top: var(--sp-3);
  border-top: 1px solid var(--line);
  font-family: var(--ff-mono);
  font-size: 9px;
  letter-spacing: 0.04em;
  color: var(--ink-2);
  line-height: 1.5;
}
.events-feed {
  margin-top: var(--sp-3);
  padding-top: var(--sp-3);
  border-top: 1px solid var(--line);
}
.feed-label {
  font-family: var(--ff-mono);
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ink-2);
  margin-bottom: 6px;
}
.events-error {
  position: sticky;
  bottom: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  background: color-mix(in srgb, var(--el-fire) 14%, var(--bg-2));
  color: var(--ink-0);
  border: 1px solid var(--el-fire);
  border-radius: 6px;
  padding: 8px var(--sp-3);
  font-size: 12px;
}
.events-error .retry-btn {
  margin-left: auto;
  background: transparent;
  border: 1px solid var(--ink-2);
  color: var(--ink-0);
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 11px;
  cursor: pointer;
}

/* ---- Stage ---- */
.stage-map {
  position: absolute;
  inset: var(--sp-4);
  display: block;
  background: var(--bg-2);
  border: 1px solid var(--line);
  border-radius: 12px;
  overflow: hidden;
  box-shadow:
    0 1px 2px rgba(26, 34, 56, 0.05),
    0 12px 32px -16px rgba(26, 34, 56, 0.18);
}
.stage-map :deep(.schematic-map-wrapper) {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  max-width: none;
  border: none;
  border-radius: 0;
  background: transparent;
  aspect-ratio: auto;
}
.stage-loading {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--ink-2);
  font-family: var(--ff-mono);
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
.loading-pulse {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--el-aether);
  opacity: 0.4;
  animation: loading-pulse 1.4s ease-in-out infinite;
}
@keyframes loading-pulse {
  0%, 100% { transform: scale(0.8); opacity: 0.35; }
  50%      { transform: scale(1.1); opacity: 0.8; }
}

/* ---- Drawer panels ---- */
.drawer-content { font-size: 13px; color: var(--ink-1); }
.drawer-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 var(--sp-4);
  font-size: var(--fz-16);
  color: var(--ink-0);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: 700;
}
.drawer-blurb {
  margin: 0 0 var(--sp-4);
  line-height: 1.55;
  color: var(--ink-1);
  font-size: 13px;
}
.drawer-blurb strong { color: var(--ink-0); font-weight: 600; }
.drawer-cite {
  margin: var(--sp-4) 0 0;
  padding-top: var(--sp-3);
  border-top: 1px solid var(--line);
  font-family: var(--ff-mono);
  font-size: 10px;
  color: var(--ink-2);
  letter-spacing: 0.04em;
  line-height: 1.6;
}

/* Result drawer (post-MC) */
.drawer-result .result-hero {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--sp-3);
  margin: var(--sp-4) 0 var(--sp-3);
}
.drawer-result .hero-stat {
  background: var(--bg-2);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: var(--sp-3) var(--sp-4);
}
.drawer-result .hero-num {
  font-family: var(--ff-mono);
  font-size: 26px;
  font-weight: 700;
  color: var(--el-aether);
  line-height: 1.05;
  font-variant-numeric: tabular-nums;
}
.drawer-result .hero-label {
  margin-top: 4px;
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--ink-2);
}
.drawer-result .hero-ci {
  margin-top: 6px;
  font-family: var(--ff-mono);
  font-size: 10px;
  color: var(--ink-2);
}
.drawer-result .best-intervention {
  background: color-mix(in srgb, var(--el-aether) 8%, var(--bg-2));
  border: 1px solid var(--el-aether);
  border-radius: 10px;
  padding: var(--sp-3) var(--sp-4);
  margin-bottom: var(--sp-3);
}
.drawer-result .bi-label {
  font-family: var(--ff-mono);
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ink-2);
}
.drawer-result .bi-name {
  margin-top: 4px;
  font-size: 14px;
  font-weight: 600;
  color: var(--ink-0);
}
.drawer-result .bi-cost {
  margin-top: 4px;
  font-family: var(--ff-mono);
  font-size: 11px;
  color: var(--ink-1);
}
.drawer-result .all-deltas {
  margin-top: var(--sp-3);
  padding-top: var(--sp-3);
  border-top: 1px solid var(--line);
}
.drawer-result .all-deltas-title {
  font-family: var(--ff-mono);
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ink-2);
  margin-bottom: var(--sp-2);
}
.drawer-result .delta-row {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  border-bottom: 1px dashed var(--line);
  font-size: 12px;
}
.drawer-result .delta-row:last-child { border-bottom: none; }
.drawer-result .dr-name { color: var(--ink-1); }
.drawer-result .dr-lives {
  color: var(--ink-0);
  font-family: var(--ff-mono);
  font-variant-numeric: tabular-nums;
}

/* Live drawer (during streaming MC) */
.drawer-live {}
.drawer-live :deep(.mc-progress-panel) {
  margin: var(--sp-3) 0;
}
.drawer-live .live-ticker-wrap {
  margin-top: var(--sp-4);
  padding-top: var(--sp-3);
  border-top: 1px solid var(--line);
}
.drawer-live .ticker-label {
  font-family: var(--ff-mono);
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ink-2);
  margin-bottom: var(--sp-2);
}

/* Gemma proposals in Result drawer */
.proposals {
  margin-top: var(--sp-4);
  padding-top: var(--sp-3);
  border-top: 1px solid var(--line);
}
.proposals-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: var(--ff-mono);
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ink-1);
  margin-bottom: var(--sp-2);
}
.proposals-status {
  margin-left: auto;
  color: var(--el-aether);
  font-style: italic;
  text-transform: none;
}
.proposals-loading {
  font-size: 12px;
  color: var(--ink-2);
  font-style: italic;
  padding: var(--sp-3);
  background: var(--bg-2);
  border-radius: 8px;
}
.proposal-card {
  background: var(--bg-2);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: var(--sp-3);
  margin-bottom: 8px;
}
.prop-row {
  display: flex;
  justify-content: space-between;
  gap: var(--sp-3);
  margin-bottom: 4px;
}
.prop-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-0);
  flex: 1;
}
.prop-cost {
  font-family: var(--ff-mono);
  font-size: 12px;
  color: var(--el-aether);
  font-variant-numeric: tabular-nums;
}
.prop-rationale {
  font-size: 11px;
  color: var(--ink-1);
  line-height: 1.4;
}
.proposals-summary {
  margin: var(--sp-3) 0 0;
  padding-top: var(--sp-2);
  border-top: 1px dashed var(--line);
  font-size: 11px;
  color: var(--ink-2);
  font-style: italic;
  line-height: 1.5;
}
.proposals-empty {
  font-size: 12px;
  color: var(--ink-2);
  font-style: italic;
}

.kv-list {
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.kv-list > div {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px dashed var(--line);
}
.kv-list dt {
  font-family: var(--ff-mono);
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ink-2);
  margin: 0;
}
.kv-list dd {
  font-size: 13px;
  color: var(--ink-0);
  font-weight: 600;
  margin: 0;
  font-variant-numeric: tabular-nums;
}
.cfg-inline {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  margin-top: var(--sp-3);
  padding-top: var(--sp-3);
  border-top: 1px solid var(--line);
}
.cfg-inline label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-family: var(--ff-mono);
  font-size: 10px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--ink-2);
}
.cfg-inline label.ck {
  flex-direction: row;
  align-items: center;
  text-transform: none;
  letter-spacing: normal;
  color: var(--ink-1);
}
.cfg-inline input[type='number'] {
  background: var(--bg-2);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 6px 10px;
  color: var(--ink-0);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}
.cfg-trials {
  display: block;
  margin-top: var(--sp-4);
  padding-top: var(--sp-3);
  border-top: 1px solid var(--line);
  font-family: var(--ff-mono);
  font-size: 10px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--ink-2);
}
.cfg-trials input {
  display: block;
  margin-top: 4px;
  background: var(--bg-2);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 6px 10px;
  color: var(--ink-0);
  font-size: 13px;
}
.chip-stack {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.chip-stack :deep(.intervention-chip) {
  width: 100%;
  justify-content: flex-start;
}

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
  display: inline-flex;
  align-items: center;
  gap: var(--sp-3);
}
.retry-btn {
  font-size: var(--fz-12);
  padding: 4px var(--sp-2);
}
.btn.ghost {
  background: transparent;
  border-color: var(--line);
}
.btn.ghost:hover:not(:disabled) {
  border-color: var(--accent);
  background: var(--bg-2);
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

/* Stack large result widgets on tablet */
@media (max-width: 1024px) {
  .delta-grid {
    grid-template-columns: 1fr;
  }
  .scenario-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 720px) {
  .aurora {
    padding: var(--sp-4) var(--sp-3);
  }
  .hdr h1 {
    font-size: var(--fz-24);
  }
  .scenario-grid {
    grid-template-columns: 1fr;
  }
  .cfg-row {
    flex-direction: column;
    align-items: stretch;
    gap: var(--sp-3);
  }
  .cfg-row label {
    flex-direction: row;
    justify-content: space-between;
    align-items: center;
  }
  .cfg-row input[type='number'] {
    width: 110px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .btn {
    transition: none;
  }
}
</style>
