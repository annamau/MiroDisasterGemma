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
      <!-- Topbar: back to cities + city/hazard chip + act indicator -->
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
      </template>

      <!-- Lateral toolbar: groups events into pills, drawer reveals detail -->
      <template #rail="{ openDrawer }">
        <EventRail
          :groups="railGroups"
          :active-id="activeDrawerId"
          :start-disabled="!canRun || loading"
          @open="(id) => { activeDrawerId = id; openDrawer(id) }"
          @start="onRunMC"
        />
      </template>

      <!-- Stage: full-bleed map (Act 2/3) — Act 4/5 will dock more here later -->
      <template #stage>
        <div v-if="loadedScenario" class="stage-map">
          <SchematicMap :scenario="loadedScenario" />
        </div>
        <div v-else class="stage-loading">
          <div class="loading-pulse"></div>
          <span>Building scenario…</span>
        </div>
      </template>

      <!-- Drawer panels: detail per rail group, GSAP slides from rail edge -->
      <template #drawer="{ drawerId }">
        <div v-if="drawerId === 'hazard'" class="drawer-content">
          <h3 class="drawer-title">
            <PhWaveSawtooth :size="16" weight="duotone" :color="`var(--el-${hazardElement})`" />
            <span>Hazard</span>
          </h3>
          <dl class="kv-list">
            <div><dt>Kind</dt><dd>{{ loadedScenario?.hazard?.kind ?? '—' }}</dd></div>
            <div v-if="loadedScenario?.hazard?.magnitude"><dt>Magnitude</dt><dd>M{{ loadedScenario.hazard.magnitude }}</dd></div>
            <div v-if="loadedScenario?.hazard?.depth_km != null"><dt>Depth</dt><dd>{{ loadedScenario.hazard.depth_km }} km</dd></div>
            <div><dt>Duration</dt><dd>{{ loadedScenario?.hazard?.duration_hours ?? '—' }} h</dd></div>
            <div><dt>Districts</dt><dd>{{ loadedScenario?.districts?.length ?? 0 }}</dd></div>
          </dl>
          <p class="drawer-cite">
            Physics: HAZUS-MH 2.1 fragility curves · Omori–Utsu aftershock chain.
          </p>
        </div>

        <div v-if="drawerId === 'population'" class="drawer-content">
          <h3 class="drawer-title">
            <PhUsersThree :size="16" weight="duotone" color="var(--el-aether)" />
            <span>Population</span>
          </h3>
          <p class="drawer-blurb">
            <strong>{{ nPopulation }}</strong> agents distributed across
            <strong>9 archetypes</strong> (eyewitness, coordinator, amplifier,
            authority, misinformer, conspiracist, helper, helpless, critic).
            Posting rates vary by phase (acute / coordination / blame).
          </p>
          <div class="cfg-inline">
            <label><span>Population</span><input type="number" v-model.number="nPopulation" min="20" max="500" /></label>
            <label><span>Hours</span><input type="number" v-model.number="durationHours" min="6" max="72" /></label>
            <label><span>Trials</span><input type="number" v-model.number="nTrials" min="1" max="64" /></label>
          </div>
          <p class="drawer-cite">
            <PhCpu :size="11" weight="duotone" color="var(--el-aether)" />
            <span>&nbsp;Gemma 4 e2b reasons over each archetype × district × phase. Cached across trials.</span>
          </p>
        </div>

        <div v-if="drawerId === 'responders'" class="drawer-content">
          <h3 class="drawer-title">
            <PhFirstAidKit :size="16" weight="duotone" color="var(--el-water)" />
            <span>Responders</span>
          </h3>
          <dl class="kv-list">
            <div><dt>Hospitals</dt><dd>{{ loadedScenario?.hospitals?.length ?? 0 }}</dd></div>
            <div><dt>Fire stations</dt><dd>{{ loadedScenario?.fire_stations?.length ?? 0 }}</dd></div>
            <div><dt>Shelters</dt><dd>{{ loadedScenario?.shelters?.length ?? 0 }}</dd></div>
          </dl>
        </div>
      </template>
    </CommandShell>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import {
  PhArrowLeft,
  PhCpu,
  PhFirstAidKit,
  PhUsersThree,
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

// Lateral rail / drawer state
const shellRef = ref(null)
const activeDrawerId = ref(null)
const heroRow = ref(null)
const deltaGrid = ref(null)
const { ctx, gsap } = useGsap(root)

const reduceMotion = () =>
  typeof window !== 'undefined' &&
  window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

// --- State ---
const scenarios = ref([])
const selectedScenarioId = ref('la-puente-hills-m72-ref')
// Interventions are no longer pre-loaded. The baseline run completes
// first; afterwards Gemma 4 reads the report and proposes targeted
// interventions to compare in the Prevention Lab. The catalog
// (`interventions`) and `selectedInterventionIds` keep their shape so
// the Prevention Lab in M6' can populate them on demand.
const interventions = ref([])
const selectedInterventionIds = ref([])
const nTrials = ref(8)
const nPopulation = ref(80)
const durationHours = ref(24)
// Gemma 4 is always on. Set during onMounted from `?gemma=off` URL param
// only as an emergency fallback; the toggle is no longer in the UI.
const useLLM = ref(true)
const loading = ref(false)
const errorMsg = ref('')

const mcRun = ref(null)
const streamRunId = ref(null)
const runState = ref('idle') // idle | running | done
const recentDecisions = ref([])

// M2: holds the full loaded scenario object (buildings, districts, facilities)
// populated by onLoadScenario; drives <SchematicMap>.
const loadedScenario = ref(null)

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
const railGroups = computed(() => {
  const s = loadedScenario.value
  const respondersTotal =
    (s?.hospitals?.length ?? 0) +
    (s?.fire_stations?.length ?? 0) +
    (s?.shelters?.length ?? 0)
  // Pre-sim rail (Acts 2/3) shows ONLY the city's three real assets:
  // hazard, population, responders. No interventions are pre-loaded —
  // Gemma proposes them after the baseline run completes (Act 5).
  return [
    {
      id: 'hazard',
      label: 'Hazard',
      stat: hazardLabel.value ?? 'Loading…',
      element: hazardElement.value,
      icon: 'WaveSawtooth',
    },
    {
      id: 'population',
      label: 'Population',
      stat: `${nPopulation.value} agents · 9 archetypes`,
      element: 'aether',
      icon: 'UsersThree',
    },
    {
      id: 'responders',
      label: 'Responders',
      stat: `${respondersTotal} responders · ${s?.hospitals?.length ?? 0} hosp`,
      element: 'water',
      icon: 'FirstAidKit',
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
  if (!selectedScenarioId.value) return
  loading.value = true
  errorMsg.value = ''
  try {
    // M2.1: Use /preview (pure in-memory scenario build, no Neo4j) to
    // populate the schematic map. The legacy /load route is Neo4j-backed
    // for graph-tools persistence — not needed for the map. Decoupling
    // means the demo runs even when Docker / Neo4j aren't up.
    const resp = await auroraApi.previewScenario(selectedScenarioId.value)
    // resp is the {success, data} envelope; resp.data is the scenario.
    if (resp?.data) loadedScenario.value = resp.data
    await loadIndex()
  } catch (e) {
    errorMsg.value = `Load failed: ${e.message}`
  } finally {
    loading.value = false
  }
}

// M2.1: auto-preview on scenario selection — no need for a "Refresh DB"
// click. The map appears as soon as the user picks a scenario.
watch(selectedScenarioId, async (newId) => {
  if (!newId) return
  // The earlier watcher clears loadedScenario; this kicks off a fresh preview.
  await onLoadScenario()
})

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

// (M2.1 collapsed: the auto-preview watch above replaces both the
// stale-clear and the explicit "Refresh DB" click. Picking a scenario
// = loading its preview into the map immediately.)

async function applyDemoSeed() {
  // ?seed=demo runs the baseline straight through; interventions are
  // proposed by Gemma post-run (no longer pre-selected).
  if (typeof window === 'undefined') return
  const params = new URLSearchParams(window.location.search)
  if (params.get('seed') !== 'demo') return
  selectedScenarioId.value = 'la-puente-hills-m72-ref'
  selectedInterventionIds.value = []
  nTrials.value = 20
  nPopulation.value = 80
  durationHours.value = 24
  currentAct.value = 2  // demo skips brand + city pick
  await loadIndex()
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
  selectedScenarioId.value = scenarioId
  // The selectedScenarioId watcher kicks off onLoadScenario(); we just advance
  // the act so the map renders as soon as the preview lands.
  goToAct(2)
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
// `?gemma=off` is the emergency fallback when Ollama is down at demo time.
function applyActFromUrl() {
  if (typeof window === 'undefined') return
  const params = new URLSearchParams(window.location.search)
  const a = parseInt(params.get('act') ?? '', 10)
  if (Number.isFinite(a) && a >= 0 && a <= 5) {
    currentAct.value = a
  }
  if (params.get('gemma') === 'off') {
    useLLM.value = false
  }
}

onMounted(async () => {
  applyActFromUrl()
  // Apply scroll lock for the (possibly URL-restored) initial act.
  if (typeof document !== 'undefined' && currentAct.value >= 2) {
    document.body.style.overflow = 'hidden'
  }
  await loadIndex()
  await applyDemoSeed()
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
}
.topbar-actindex .ai-num { color: var(--ink-0); font-weight: 600; }

/* ---- Stage ---- */
.stage-map {
  position: absolute;
  inset: var(--sp-4);
  display: block;
  background:
    linear-gradient(180deg,
      color-mix(in srgb, var(--bg-0) 80%, transparent) 0%,
      color-mix(in srgb, var(--bg-1) 60%, transparent) 100%);
  border: 1px solid var(--line);
  border-radius: 12px;
  overflow: hidden;
  box-shadow:
    inset 0 0 0 1px color-mix(in srgb, var(--ink-0) 4%, transparent),
    0 24px 48px -16px rgba(0, 0, 0, 0.45);
}
/* Subtle paper-grid layer behind the SVG so the city reads as a view,
   not as chrome that swallowed it. */
.stage-map::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(var(--line) 1px, transparent 1px),
    linear-gradient(90deg, var(--line) 1px, transparent 1px);
  background-size: 56px 56px;
  opacity: 0.35;
  mask-image: radial-gradient(ellipse at center, rgba(0,0,0,0.85) 0%, transparent 80%);
  pointer-events: none;
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
  z-index: 1;
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
