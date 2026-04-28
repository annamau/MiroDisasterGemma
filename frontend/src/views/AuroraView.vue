<template>
  <div class="aurora">
    <header class="hdr">
      <h1>Aurora — City Resilience Digital Twin</h1>
      <p class="sub">
        Pick a hazard scenario, toggle prevention interventions, run a Monte Carlo
        — see lives saved and dollars saved with 90% CI.
      </p>
    </header>

    <section class="row">
      <div class="card">
        <h2>1. Scenario</h2>
        <div v-if="!scenarios.length" class="muted">Loading…</div>
        <div v-else class="scenarios">
          <label v-for="s in scenarios" :key="s.scenario_id" class="opt">
            <input
              type="radio"
              v-model="selectedScenarioId"
              :value="s.scenario_id"
            />
            <span>{{ s.scenario_id }}</span>
            <span
              class="badge"
              :class="{ ok: s.loaded_in_db, off: !s.loaded_in_db }"
            >
              {{ s.loaded_in_db ? 'in DB' : 'not loaded' }}
            </span>
          </label>
          <button class="btn" :disabled="loading" @click="onLoadScenario">
            {{ loading ? 'Loading…' : 'Load / refresh' }}
          </button>
          <button
            class="btn ghost"
            :disabled="!selectedScenarioId || loading"
            @click="onBaselineLoss"
          >
            Show deterministic baseline
          </button>
        </div>
        <pre v-if="baseline" class="kv">{{ formatBaseline(baseline) }}</pre>
      </div>

      <div class="card">
        <h2>2. Interventions</h2>
        <div v-if="!interventions.length" class="muted">Loading…</div>
        <label v-for="iv in interventions" :key="iv.intervention_id" class="opt">
          <input
            type="checkbox"
            :value="iv.intervention_id"
            v-model="selectedInterventionIds"
            :disabled="iv.intervention_id === 'baseline'"
          />
          <span class="lbl">{{ iv.label }}</span>
          <span class="kind">{{ iv.kind }}</span>
        </label>

        <div class="cfg">
          <label>
            N trials
            <input type="number" v-model.number="nTrials" min="1" max="200" />
          </label>
          <label>
            Population
            <input type="number" v-model.number="nPopulation" min="20" max="500" />
          </label>
          <label>
            Hours
            <input type="number" v-model.number="durationHours" min="6" max="72" />
          </label>
          <label class="ck">
            <input type="checkbox" v-model="useLLM" />
            <span>Use Gemma 4 (e2b) for population decisions</span>
          </label>
        </div>

        <button class="btn primary" :disabled="loading || !canRun" @click="onRunMC">
          {{ loading ? 'Running Monte Carlo…' : 'Run Monte Carlo' }}
        </button>
      </div>
    </section>

    <section v-if="mcRun" class="card wide">
      <h2>3. Outcome Comparator</h2>
      <p class="muted">
        N={{ mcRun.n_trials }} trials per arm · duration={{ mcRun.duration_hours }}h ·
        wall={{ mcRun.wall_seconds }}s · cache_hit={{ Math.round(mcRun.baseline.cache_hit_rate * 100) }}%
      </p>

      <table class="cmp">
        <thead>
          <tr>
            <th>Intervention</th>
            <th>Lives saved</th>
            <th>Dollars saved</th>
            <th>Misinfo Δ</th>
            <th>$/life</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><b>Baseline</b> (no intervention)</td>
            <td>{{ mcRun.baseline.deaths.point.toFixed(0) }} deaths</td>
            <td>${{ (mcRun.baseline.economic_loss_usd.point / 1e9).toFixed(2) }}B loss</td>
            <td>{{ mcRun.baseline.misinfo_ratio.point.toFixed(1) }}× ratio</td>
            <td>—</td>
          </tr>
          <tr v-for="d in mcRun.deltas" :key="d.intervention_id">
            <td>{{ d.label }}</td>
            <td :class="cssDelta(d.lives_saved.point)">
              <b>{{ d.lives_saved.point.toFixed(0) }}</b>
              <span class="ci">[{{ d.lives_saved.lo.toFixed(0) }}, {{ d.lives_saved.hi.toFixed(0) }}]</span>
            </td>
            <td :class="cssDelta(d.dollars_saved.point)">
              <b>${{ (d.dollars_saved.point / 1e9).toFixed(2) }}B</b>
              <span class="ci">
                [${{ (d.dollars_saved.lo / 1e9).toFixed(2) }}B,
                ${{ (d.dollars_saved.hi / 1e9).toFixed(2) }}B]
              </span>
            </td>
            <td :class="cssDelta(d.misinfo_ratio_change.point)">
              {{ d.misinfo_ratio_change.point.toFixed(2) }}
            </td>
            <td>{{ d.cost_per_life_saved_usd ? `$${(d.cost_per_life_saved_usd / 1e3).toFixed(0)}K` : '—' }}</td>
          </tr>
        </tbody>
      </table>

      <h3>Cumulative deaths (mean across trials)</h3>
      <svg class="chart" :viewBox="`0 0 ${chartW} ${chartH}`">
        <g v-for="(line, i) in chartLines" :key="i">
          <polyline
            :points="line.points"
            :stroke="line.color"
            stroke-width="2"
            fill="none"
          />
        </g>
        <g class="axis">
          <line :x1="40" :y1="chartH - 30" :x2="chartW - 10" :y2="chartH - 30" stroke="#aaa" />
          <line :x1="40" :y1="10" :x2="40" :y2="chartH - 30" stroke="#aaa" />
          <text :x="50" :y="chartH - 12" font-size="10" fill="#888">hours</text>
          <text :x="6" :y="20" font-size="10" fill="#888">deaths</text>
        </g>
      </svg>

      <ul class="legend">
        <li v-for="(line, i) in chartLines" :key="i">
          <span class="sw" :style="{ background: line.color }"></span>
          {{ line.label }}
        </li>
      </ul>
    </section>

    <p v-if="errorMsg" class="err">{{ errorMsg }}</p>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { auroraApi } from '../api/aurora.js'

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

const baseline = ref(null)
const mcRun = ref(null)

const chartW = 720
const chartH = 240

const canRun = computed(
  () => !!selectedScenarioId.value && selectedInterventionIds.value.length > 0,
)

function cssDelta(v) {
  if (v > 0) return 'pos'
  if (v < 0) return 'neg'
  return ''
}

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

async function onBaselineLoss() {
  if (!selectedScenarioId.value) return
  loading.value = true
  errorMsg.value = ''
  try {
    const resp = await auroraApi.baselineLoss(selectedScenarioId.value)
    baseline.value = resp.data
  } catch (e) {
    errorMsg.value = `Baseline failed: ${e.message}`
  } finally {
    loading.value = false
  }
}

async function onRunMC() {
  loading.value = true
  errorMsg.value = ''
  mcRun.value = null
  try {
    const resp = await auroraApi.runMonteCarlo(selectedScenarioId.value, {
      intervention_ids: selectedInterventionIds.value,
      n_trials: nTrials.value,
      duration_hours: durationHours.value,
      n_population_agents: nPopulation.value,
      use_llm: useLLM.value,
    })
    mcRun.value = resp.data
  } catch (e) {
    errorMsg.value = `MC run failed: ${e.message}`
  } finally {
    loading.value = false
  }
}

function formatBaseline(b) {
  return JSON.stringify(b, null, 2)
}

const COLORS = ['#666', '#10b981', '#3b82f6', '#a855f7', '#f97316', '#ef4444']

const chartLines = computed(() => {
  if (!mcRun.value) return []
  const out = []
  const series = [
    { label: 'baseline', tl: mcRun.value.baseline.deaths_timeline_mean },
    ...mcRun.value.interventions.map((o) => ({
      label: o.label,
      tl: o.deaths_timeline_mean,
    })),
  ]
  const max = Math.max(...series.map((s) => Math.max(...s.tl)))
  series.forEach((s, idx) => {
    const points = s.tl
      .map((y, x) => {
        const px = 40 + (x / Math.max(1, s.tl.length - 1)) * (chartW - 50)
        const py = chartH - 30 - (y / max) * (chartH - 50)
        return `${px.toFixed(1)},${py.toFixed(1)}`
      })
      .join(' ')
    out.push({ label: s.label, color: COLORS[idx % COLORS.length], points })
  })
  return out
})

onMounted(loadIndex)
</script>

<style scoped>
.aurora {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
  font-family:
    -apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, Roboto, sans-serif;
  color: #1f2937;
}
.hdr h1 {
  margin: 0 0 4px;
  font-size: 24px;
}
.sub {
  margin: 0 0 24px;
  color: #6b7280;
}
.row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}
.card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 16px;
}
.card.wide {
  grid-column: 1 / -1;
}
.card h2 {
  margin-top: 0;
  font-size: 16px;
  color: #111827;
}
.opt {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  font-size: 14px;
}
.opt input[type='radio'],
.opt input[type='checkbox'] {
  margin: 0;
}
.lbl {
  flex: 1;
}
.kind {
  font-size: 11px;
  color: #6b7280;
  background: #f3f4f6;
  padding: 1px 6px;
  border-radius: 6px;
}
.badge {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 6px;
}
.badge.ok {
  background: #d1fae5;
  color: #065f46;
}
.badge.off {
  background: #fee2e2;
  color: #991b1b;
}
.cfg {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 8px;
  margin: 12px 0;
  font-size: 13px;
}
.cfg label {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.cfg input {
  padding: 4px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
}
.cfg .ck {
  grid-column: 1 / -1;
  flex-direction: row;
  align-items: center;
}
.btn {
  background: #f3f4f6;
  border: 1px solid #d1d5db;
  padding: 8px 14px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
}
.btn.primary {
  background: #2563eb;
  color: white;
  border-color: #2563eb;
  margin-top: 12px;
}
.btn.ghost {
  background: transparent;
}
.btn[disabled] {
  opacity: 0.5;
  cursor: not-allowed;
}
.kv {
  background: #f9fafb;
  padding: 8px;
  border-radius: 6px;
  font-size: 11px;
  max-height: 240px;
  overflow: auto;
  margin-top: 8px;
}
.cmp {
  width: 100%;
  font-size: 13px;
  border-collapse: collapse;
  margin-top: 8px;
}
.cmp th,
.cmp td {
  padding: 6px 8px;
  text-align: left;
  border-bottom: 1px solid #e5e7eb;
}
.cmp .pos {
  color: #059669;
}
.cmp .neg {
  color: #dc2626;
}
.ci {
  color: #6b7280;
  font-size: 11px;
  margin-left: 4px;
}
.muted {
  color: #6b7280;
  font-size: 12px;
}
.err {
  color: #dc2626;
  font-size: 13px;
  margin-top: 8px;
}
.chart {
  width: 100%;
  height: 240px;
  margin-top: 8px;
  background: #f9fafb;
  border-radius: 6px;
}
.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 12px;
  list-style: none;
  padding: 8px 0 0;
  margin: 0;
  color: #4b5563;
}
.sw {
  display: inline-block;
  width: 12px;
  height: 4px;
  margin-right: 4px;
  vertical-align: middle;
  border-radius: 2px;
}
</style>
