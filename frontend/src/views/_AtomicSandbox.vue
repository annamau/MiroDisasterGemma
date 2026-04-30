<template>
  <div class="sandbox">
    <h1>Atomic Component Sandbox (P-V2)</h1>

    <!-- ElementBadge all elements + sizes -->
    <section>
      <h2>ElementBadge</h2>
      <div class="row wrap">
        <div v-for="el in elements" :key="el" class="col">
          <div class="el-label">{{ el }}</div>
          <div class="row" v-for="sz in [16, 20, 24, 32, 48]" :key="sz">
            <ElementBadge :element="el" :icon="elementIcon[el]" :size="sz" />
            <span class="size-tag">{{ sz }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- ScenarioCard -->
    <section>
      <h2>ScenarioCard</h2>
      <div class="card-grid">
        <ScenarioCard
          v-for="s in demoScenarios"
          :key="s.scenario_id"
          :scenario="s"
          :selected="selectedScenario === s.scenario_id"
          @select="selectedScenario = $event"
        />
      </div>
    </section>

    <!-- InterventionChip -->
    <section>
      <h2>InterventionChip</h2>
      <div class="row wrap gap">
        <InterventionChip
          v-for="iv in demoInterventions"
          :key="iv.intervention_id"
          :intervention="iv"
          :selected="selectedChips.includes(iv.intervention_id)"
          :disabled="iv.intervention_id === 'baseline'"
          @toggle="toggleChip"
        />
      </div>
    </section>

    <!-- RunButton states -->
    <section>
      <h2>RunButton</h2>
      <div class="row gap">
        <RunButton :state="btnStates[btnIdx]" label="Run Monte Carlo" @click="cycleBtnState" />
        <RunButton state="running" label="Run Monte Carlo" />
        <RunButton :state="doneBtnState" label="Run Monte Carlo" @click="triggerDone" />
        <RunButton state="idle" label="Disabled" :disabled="true" />
      </div>
      <p class="note">Click the first button to cycle states. Click the third to trigger "done" flash.</p>
    </section>

    <!-- P-V3 streaming demo: synthetic progress, no backend needed -->
    <section>
      <h2>MCProgressPanel + AgentLogTicker (P-V3 streaming)</h2>
      <div class="row gap">
        <button class="sandbox-btn" @click="simulateStreaming">Simulate streaming run</button>
        <button class="sandbox-btn" @click="resetStreaming">Reset</button>
      </div>
      <div class="streaming-grid">
        <MCProgressPanel
          :run-id="streamingRunId"
          scenario-id="sandbox-fake"
          :arms="streamingArms"
          :mock-arm-state="streamingArmState"
        />
        <AgentLogTicker :decisions="syntheticDecisions" />
      </div>
      <p class="note">
        The progress bars and decision feed are driven by an in-component
        setInterval — no backend required. Watch the bars tween smoothly
        and the agent log scroll new entries in.
      </p>
    </section>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import ElementBadge from '../components/aurora/ElementBadge.vue'
import ScenarioCard from '../components/aurora/ScenarioCard.vue'
import InterventionChip from '../components/aurora/InterventionChip.vue'
import RunButton from '../components/aurora/RunButton.vue'
import MCProgressPanel from '../components/aurora/MCProgressPanel.vue'
import AgentLogTicker from '../components/aurora/AgentLogTicker.vue'

const elements = ['fire', 'water', 'earth', 'air', 'aether']

const elementIcon = {
  fire: 'Flame',
  water: 'WaveTriangle',
  earth: 'Mountains',
  air: 'Wind',
  aether: 'Users',
}

const demoScenarios = [
  {
    scenario_id: 'la-puente-hills-m72-ref',
    label: 'LA Puente Hills M7.2',
    sub: 'Southern California megathrust — reference scenario',
    element: 'earth',
    icon: 'Mountains',
    loaded_in_db: true,
    hazard_params: { Mw: '7.2', depth: '17km', 'PGA-max': '0.62g', duration: '24h' },
  },
  {
    scenario_id: 'la-wildfire-santa-ana',
    label: 'LA Wildfire — Santa Ana',
    sub: '70mph gusts, red-flag conditions',
    element: 'fire',
    icon: 'Flame',
    loaded_in_db: false,
    hazard_params: { 'wind-mph': '70', 'rh%': '8', acres: '12k', duration: '48h' },
  },
  {
    scenario_id: 'socal-flood-arx',
    label: 'SoCal Flash Flood',
    sub: 'Atmospheric river extreme — 1-in-100yr',
    element: 'water',
    icon: 'WaveTriangle',
    loaded_in_db: true,
    hazard_params: { 'precip-in': '9.4', flow: '28k cfs', duration: '18h' },
  },
  {
    scenario_id: 'hurricane-diana-cat4',
    label: 'Hurricane Diana Cat-4',
    sub: 'Gulf landfall — 145mph sustained',
    element: 'air',
    icon: 'Wind',
    loaded_in_db: false,
    hazard_params: { 'wind-mph': '145', 'surge-ft': '14', track: 'direct', duration: '72h' },
  },
  {
    scenario_id: 'pop-displacement-aether',
    label: 'Population Displacement',
    sub: 'Multi-hazard social cascade scenario',
    element: 'aether',
    icon: 'Users',
    loaded_in_db: true,
    hazard_params: { displaced: '80k', archetype: '5', duration: '24h' },
  },
]

const demoInterventions = [
  { intervention_id: 'baseline', label: 'Baseline (no intervention)', kind: 'control', element: 'air', icon: 'Siren' },
  { intervention_id: 'preposition_d03_4amb', label: 'Pre-position 4 Ambulances', kind: 'medical', element: 'aether', icon: 'FirstAidKit' },
  { intervention_id: 'evac_d03_30min_early', label: 'Evacuation 30min Early', kind: 'evacuation', element: 'earth', icon: 'ClockClockwise' },
  { intervention_id: 'retrofit_d03_w1', label: 'Seismic Retrofit W1', kind: 'infrastructure', element: 'earth', icon: 'Buildings' },
  { intervention_id: 'prebunk_misinfo', label: 'Prebunk Misinfo Campaign', kind: 'communication', element: 'aether', icon: 'ChatCircleDots' },
  { intervention_id: 'fire_break_d03', label: 'Firebreak — Zone D03', kind: 'physical', element: 'fire', icon: 'Flame' },
]

const selectedScenario = ref('la-puente-hills-m72-ref')
const selectedChips = ref(['preposition_d03_4amb', 'evac_d03_30min_early', 'retrofit_d03_w1', 'prebunk_misinfo'])

function toggleChip(id) {
  const idx = selectedChips.value.indexOf(id)
  if (idx === -1) selectedChips.value.push(id)
  else selectedChips.value.splice(idx, 1)
}

const btnStates = ['idle', 'running', 'done']
const btnIdx = ref(0)
function cycleBtnState() {
  btnIdx.value = (btnIdx.value + 1) % btnStates.length
}

const doneBtnState = ref('idle')
function triggerDone() {
  doneBtnState.value = 'running'
  setTimeout(() => { doneBtnState.value = 'done' }, 800)
  setTimeout(() => { doneBtnState.value = 'idle' }, 3000)
}

// ---- P-V3 streaming sandbox ----
const streamingArms = [
  { intervention_id: 'preposition_d03_4amb', label: 'Pre-position 4 Ambulances', element: 'aether', icon: 'FirstAidKit', n_trials: 30 },
  { intervention_id: 'evac_d03_30min_early', label: 'Evacuation 30min Early', element: 'earth', icon: 'ClockClockwise', n_trials: 30 },
  { intervention_id: 'retrofit_d03_w1', label: 'Seismic Retrofit W1', element: 'earth', icon: 'Buildings', n_trials: 30 },
  { intervention_id: 'baseline', label: 'Baseline', element: 'air', icon: 'Siren', n_trials: 30 },
]
const streamingRunId = ref(null) // null = use mock mode
const streamingArmState = ref({})
const syntheticDecisions = ref([])
let streamTimer = null

const SYNTH_LINES = [
  { archetype: 'eyewitness', district_id: 'LA-D03', post_text: 'lights flickering, no comms here' },
  { archetype: 'helper', district_id: 'LA-D02', post_text: 'heading to elementary on 7th, anyone need rides' },
  { archetype: 'amplifier', district_id: 'LA-D01', post_text: 'RT BOOST: shelter at @municipal_court is OPEN' },
  { archetype: 'authority', district_id: 'LA-D03', post_text: 'mandatory evac order issued for zones A through D' },
  { archetype: 'vulnerable', district_id: 'LA-D04', post_text: 'cant reach my daughter in the valley' },
  { archetype: 'eyewitness', district_id: 'LA-D03', post_text: 'building swaying, dust everywhere' },
  { archetype: 'helper', district_id: 'LA-D05', post_text: 'medical team staged at Maple parking lot' },
]

function simulateStreaming() {
  resetStreaming()
  streamingArms.forEach((arm) => {
    streamingArmState.value[arm.intervention_id] = {
      trials_done: 0,
      trials_total: arm.n_trials,
      deaths_running_mean: 0,
    }
  })
  let tick = 0
  streamTimer = setInterval(() => {
    tick += 1
    let allDone = true
    for (const arm of streamingArms) {
      const cur = streamingArmState.value[arm.intervention_id]
      if (cur.trials_done < cur.trials_total) {
        cur.trials_done = Math.min(cur.trials_total, cur.trials_done + 1 + Math.floor(Math.random() * 2))
        cur.deaths_running_mean = 12 + Math.random() * 8 - (arm.intervention_id === 'baseline' ? 0 : 4)
        allDone = false
      }
    }
    streamingArmState.value = { ...streamingArmState.value }
    if (tick % 2 === 0 && tick < 30) {
      const next = SYNTH_LINES[(tick / 2) % SYNTH_LINES.length]
      const hour = (tick * 2) % 24
      const minute = (tick * 7) % 60
      syntheticDecisions.value = [
        { ...next, hour, minute, timestamp: Date.now() / 1000 },
        ...syntheticDecisions.value,
      ].slice(0, 8)
    }
    if (allDone) {
      clearInterval(streamTimer)
      streamTimer = null
    }
  }, 350)
}

function resetStreaming() {
  if (streamTimer) clearInterval(streamTimer)
  streamTimer = null
  streamingArmState.value = {}
  syntheticDecisions.value = []
}
</script>

<style scoped>
.sandbox {
  padding: 32px;
  background: var(--bg-0);
  color: var(--ink-0);
  min-height: 100vh;
  font-family: 'Inter Variable', Inter, sans-serif;
}

h1 {
  font-size: var(--fz-24);
  margin: 0 0 var(--sp-8);
  color: var(--ink-0);
  font-weight: 700;
}

section {
  margin-bottom: var(--sp-12);
}

h2 {
  font-size: var(--fz-16);
  color: var(--ink-1);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin: 0 0 var(--sp-4);
  font-weight: 600;
}

.row {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
}

.wrap {
  flex-wrap: wrap;
}

.gap {
  gap: var(--sp-3);
}

.col {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  padding: var(--sp-4);
  background: var(--bg-1);
  border-radius: 8px;
  border: 1px solid var(--line);
}

.el-label {
  font-size: var(--fz-12);
  font-weight: 600;
  color: var(--ink-2);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: var(--sp-1);
}

.size-tag {
  font-size: 10px;
  color: var(--ink-2);
  font-variant-numeric: tabular-nums;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--sp-4);
}

.note {
  font-size: var(--fz-12);
  color: var(--ink-2);
  margin-top: var(--sp-3);
}

.streaming-grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
  gap: var(--sp-4);
  margin-top: var(--sp-3);
}

@media (max-width: 800px) {
  .streaming-grid {
    grid-template-columns: 1fr;
  }
}

.sandbox-btn {
  background: var(--bg-2);
  color: var(--ink-0);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: var(--sp-2) var(--sp-3);
  font-size: var(--fz-12);
  font-weight: 500;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}
.sandbox-btn:hover {
  border-color: var(--el-aether-glow);
  background: var(--bg-1);
}
</style>
