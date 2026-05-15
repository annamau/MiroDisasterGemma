// SPDX-License-Identifier: Apache-2.0
//
// Phase 2b — Act 5 Prevention Lab UI
// ==================================
// These tests cover the interactive layer added on top of Phase 1's
// per-scenario state map. The Phase 2b features under test:
//
//   1. `derivedAct` computed that drives the topbar pill (2/3/4/5)
//      from runState + mcRun + selectedInterventionIds.
//   2. Clickable proposal cards that toggle membership in
//      selectedInterventionIds via `toggleProposal` / `toggleIntervention`.
//   3. The "Re-run with N selected · +$X.YM" CTA that is disabled when
//      0 proposals are selected, and shows a cost total.
//   4. The new Act 5 events-panel section: a 2-col DeltaCard grid
//      driven by `enrichedDeltas`.
//   5. `mcRunHistory` push semantics in `onRunMC`: the previous
//      best delta is captured BEFORE the state wipe, capped at 3
//      entries FIFO.
//   6. Misuse:
//      - Re-run with 0 selected fires no network request.
//      - 5 rapid Re-run clicks dedupe to 1 backend POST.
//      - Backend "already_running" response does NOT wipe mcRun.
//
// All API calls are mocked — no real HTTP fires.
//
// (Phase 1's tests live next door in AuroraView.state.spec.js; this file
// targets ONLY the additive Phase 2b surface so the two specs stay
// independent.)

import { describe, it, test, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

// Mock the API module BEFORE importing AuroraView.
vi.mock('@/api/aurora', () => {
  return {
    auroraApi: {
      listScenarios: vi.fn().mockResolvedValue({
        data: {
          scenarios: [
            { scenario_id: 'la-puente-hills-m72-ref', label: 'LA' },
            { scenario_id: 'valencia-dana-2024', label: 'Valencia' },
          ],
        },
      }),
      listInterventions: vi.fn().mockResolvedValue({
        data: { interventions: [] },
      }),
      previewScenario: vi.fn().mockImplementation((scenarioId) =>
        Promise.resolve({
          data: {
            scenario_id: scenarioId,
            city: scenarioId,
            hazard: { kind: 'earthquake', magnitude: 7.2, duration_hours: 24 },
            districts: [],
            buildings: [],
            hospitals: [],
            fire_stations: [],
            shelters: [],
          },
        }),
      ),
      runMCStreaming: vi.fn().mockResolvedValue({
        data: { run_id: 'mock-run-id', status: 'started' },
      }),
      getMCProgress: vi.fn().mockResolvedValue({
        success: true,
        data: { arms: {}, done: false, recent_decisions: [], error: null },
      }),
      getMCResult: vi.fn().mockResolvedValue({
        success: true,
        data: {},
      }),
      proposeInterventions: vi.fn().mockResolvedValue({
        data: { proposals: [], summary: '', model: 'mock' },
      }),
      loadScenario: vi.fn().mockResolvedValue({ data: {} }),
      baselineLoss: vi.fn().mockResolvedValue({ data: {} }),
      runMonteCarlo: vi.fn().mockResolvedValue({ data: {} }),
    },
  }
})

const importView = () => import('@/views/AuroraView.vue')

async function mountView({ url } = {}) {
  if (url && typeof window !== 'undefined') {
    window.history.replaceState({}, '', url)
  }
  const { default: AuroraView } = await importView()
  const wrapper = mount(AuroraView, {
    attachTo: document.body,
    global: {
      stubs: {
        CommandShell: {
          template:
            '<div><slot name="topbar" /><slot name="rail" /><slot name="stage" /><slot name="events" /><slot /></div>',
        },
        EventRail: { template: '<div />' },
        ScenarioCard: { template: '<div />' },
        InterventionChip: { template: '<div />' },
        RunButton: { template: '<div />' },
        SkeletonCard: { template: '<div />' },
        MCProgressPanel: { template: '<div />' },
        AgentLogTicker: { template: '<div />' },
        HeroNumber: { template: '<div />' },
        // DeltaCard is the one we explicitly DO NOT stub — Phase 2b's
        // act5-grid uses real DeltaCards. We stub-render its minimum so
        // it's findable in the DOM without doing layout work.
        DeltaCard: {
          name: 'DeltaCard',
          props: ['delta'],
          template:
            '<div class="delta-card" :data-intervention-id="delta?.intervention_id">{{ delta?.label }}</div>',
        },
        ComparatorTable: { template: '<div />' },
        CumulativeChart: { template: '<div />' },
        SchematicMap: { template: '<div />' },
        Act0Brief: { template: '<div />' },
        Act1CityPick: { template: '<div />' },
      },
    },
  })
  await flushPromises()
  return { wrapper, setup: wrapper.vm.$.setupState }
}

// Fixtures for a typical post-MC state.
function makeMcRun({ deltas = null } = {}) {
  return {
    n_trials: 8,
    duration_hours: 24,
    baseline: {
      deaths: { point: 200, lo: 180, hi: 220 },
      injuries: { point: 1200, lo: 1000, hi: 1400 },
      economic_loss_usd: { point: 1.2e9, lo: 1.0e9, hi: 1.4e9 },
      deaths_timeline_mean: new Array(24).fill(8),
    },
    interventions: deltas
      ? deltas.map((d) => ({
          intervention_id: d.intervention_id,
          label: d.label,
          deaths_timeline_mean: new Array(24).fill(5),
        }))
      : [],
    deltas:
      deltas ?? [
        // single demo delta when caller didn't override
        {
          intervention_id: 'evac_d03_30min_early',
          label: 'Evacuation +30 min',
          lives_saved: { point: 1871, lo: 1500, hi: 2240 },
          dollars_saved: { point: 12.3e6, lo: 9e6, hi: 16e6 },
          cost_per_life_saved_usd: 228,
          misinfo_ratio_change: { point: -0.1, lo: -0.2, hi: 0 },
        },
      ],
  }
}

function makeProposals(ids = ['evac_d03_30min_early', 'retrofit_d03_w1']) {
  const labels = {
    evac_d03_30min_early: 'Evacuation +30 min',
    retrofit_d03_w1: 'Retrofit W1 buildings',
    preposition_d03_4amb: 'Preposition 4 ambulances',
  }
  const costs = {
    evac_d03_30min_early: 250_000,
    retrofit_d03_w1: 4_200_000,
    preposition_d03_4amb: 120_000,
  }
  return {
    proposals: ids.map((id) => ({
      intervention_id: id,
      label: labels[id] ?? id,
      kind: 'mitigation',
      rationale: `Why we recommend ${id}`,
      cost_usd: costs[id] ?? 100_000,
      cost_source: 'catalog',
    })),
    summary: 'Pick at least one and Re-run.',
    model: 'mock',
    generated_at: '2024-01-01T00:00:00Z',
  }
}

beforeEach(() => {
  if (typeof window !== 'undefined') {
    window.history.replaceState({}, '', '/')
    const store = new Map()
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: {
        getItem: (k) => (store.has(k) ? store.get(k) : null),
        setItem: (k, v) => store.set(k, String(v)),
        removeItem: (k) => store.delete(k),
        clear: () => store.clear(),
      },
    })
  }
  vi.clearAllMocks()
})

afterEach(() => {
  document.body.innerHTML = ''
})

// ---------------------------------------------------------------------------
// U1 — derivedAct: full transition table from briefing through Act 5
// ---------------------------------------------------------------------------
describe('Phase 2b — derivedAct transitions', () => {
  test('U1: derivedAct = 2 when no mcRun and act >= 2', async () => {
    const { setup } = await mountView()
    // Force into shell mode (Acts 2..5 are derived).
    setup.currentAct = 2
    await nextTick()
    expect(setup.derivedAct).toBe(2)
  })

  test('U1b: derivedAct = 3 when runState = running', async () => {
    const { setup } = await mountView()
    setup.currentAct = 2
    setup.setForCurrent('runState', 'running')
    await nextTick()
    expect(setup.derivedAct).toBe(3)
  })

  test('U1c: derivedAct = 4 when done + 0 selected', async () => {
    const { setup } = await mountView()
    setup.currentAct = 2
    setup.setForCurrent('mcRun', makeMcRun())
    setup.setForCurrent('runState', 'done')
    setup.setForCurrent('selectedInterventionIds', [])
    await nextTick()
    expect(setup.derivedAct).toBe(4)
  })

  test('U1d: derivedAct = 5 when done + 1+ selected + deltas present', async () => {
    const { setup } = await mountView()
    setup.currentAct = 2
    setup.setForCurrent('mcRun', makeMcRun())
    setup.setForCurrent('runState', 'done')
    setup.setForCurrent('selectedInterventionIds', ['evac_d03_30min_early'])
    await nextTick()
    expect(setup.derivedAct).toBe(5)
  })

  test('U1e: derivedAct preserves Acts 0/1 (brand + city pick)', async () => {
    const { setup } = await mountView()
    setup.currentAct = 0
    await nextTick()
    expect(setup.derivedAct).toBe(0)
    setup.currentAct = 1
    await nextTick()
    expect(setup.derivedAct).toBe(1)
  })
})

// ---------------------------------------------------------------------------
// U2 — Clicking unselected proposal pushes id; clicking again removes
// ---------------------------------------------------------------------------
describe('Phase 2b — proposal toggle', () => {
  test('U2: toggleProposal adds and removes from selectedInterventionIds', async () => {
    const { setup } = await mountView()
    // selectedInterventionIds starts empty for LA (per Phase 1 spec).
    expect(setup.selectedInterventionIds).toEqual([])

    setup.toggleProposal('evac_d03_30min_early')
    await nextTick()
    expect(setup.selectedInterventionIds).toEqual(['evac_d03_30min_early'])

    setup.toggleProposal('evac_d03_30min_early')
    await nextTick()
    expect(setup.selectedInterventionIds).toEqual([])
  })
})

// ---------------------------------------------------------------------------
// U3 — Re-run button disabled when 0 selected
// ---------------------------------------------------------------------------
describe('Phase 2b — re-run CTA', () => {
  test('U3: rerun-button is disabled when selectedInterventionIds is empty', async () => {
    const { wrapper, setup } = await mountView()
    setup.currentAct = 2
    setup.setForCurrent('mcRun', makeMcRun())
    setup.setForCurrent('runState', 'done')
    setup.setForCurrent('proposedInterventions', makeProposals())
    setup.setForCurrent('selectedInterventionIds', [])
    await nextTick()

    const btn = wrapper.find('.rerun-button')
    expect(btn.exists()).toBe(true)
    expect(btn.element.disabled).toBe(true)
  })

  test('U4: rerun button label reads "Re-run with N selected · +$X.YM"', async () => {
    const { wrapper, setup } = await mountView()
    setup.currentAct = 2
    setup.setForCurrent('mcRun', makeMcRun())
    setup.setForCurrent('runState', 'done')
    setup.setForCurrent('proposedInterventions', makeProposals())
    setup.setForCurrent('selectedInterventionIds', [
      'evac_d03_30min_early',
      'retrofit_d03_w1',
    ])
    await nextTick()

    const btn = wrapper.find('.rerun-button')
    expect(btn.exists()).toBe(true)
    expect(btn.element.disabled).toBe(false)
    const txt = btn.text()
    // Label needs to surface count AND cost — exact format is owned by the
    // template (e.g. "Re-run with 2 selected · +$4.5M") so we assert the
    // two semantic pieces, not literal punctuation.
    expect(txt).toContain('2 selected')
    expect(txt).toMatch(/\+\$[\d.]+M/)
  })
})

// ---------------------------------------------------------------------------
// U5 — Act 5 grid renders one DeltaCard per delta
// ---------------------------------------------------------------------------
describe('Phase 2b — Act 5 grid', () => {
  test('U5: act5-grid contains one DeltaCard per enriched delta', async () => {
    const { wrapper, setup } = await mountView()
    setup.currentAct = 2
    const deltas = [
      {
        intervention_id: 'evac_d03_30min_early',
        label: 'Evac',
        lives_saved: { point: 1500, lo: 1200, hi: 1800 },
        dollars_saved: { point: 10e6, lo: 8e6, hi: 12e6 },
        cost_per_life_saved_usd: 300,
        misinfo_ratio_change: { point: 0, lo: 0, hi: 0 },
      },
      {
        intervention_id: 'retrofit_d03_w1',
        label: 'Retrofit',
        lives_saved: { point: 800, lo: 600, hi: 1000 },
        dollars_saved: { point: 6e6, lo: 5e6, hi: 7e6 },
        cost_per_life_saved_usd: 1200,
        misinfo_ratio_change: { point: 0, lo: 0, hi: 0 },
      },
    ]
    setup.setForCurrent('mcRun', makeMcRun({ deltas }))
    setup.setForCurrent('runState', 'done')
    setup.setForCurrent('selectedInterventionIds', [
      'evac_d03_30min_early',
      'retrofit_d03_w1',
    ])
    await nextTick()

    expect(setup.derivedAct).toBe(5)
    const cards = wrapper.findAll('.act5-grid .delta-card')
    expect(cards.length).toBe(2)
    // Verify ordering / mapping
    const ids = cards.map((c) => c.attributes('data-intervention-id')).sort()
    expect(ids).toEqual(['evac_d03_30min_early', 'retrofit_d03_w1'])
  })
})

// ---------------------------------------------------------------------------
// U6/U7 — mcRunHistory push semantics
// ---------------------------------------------------------------------------
describe('Phase 2b — mcRunHistory push', () => {
  test('U7: onRunMC saves previous best delta to history before clearing', async () => {
    const { setup } = await mountView()
    // Arrange a finished run on LA.
    setup.setForCurrent(
      'mcRun',
      makeMcRun({
        deltas: [
          {
            intervention_id: 'evac_d03_30min_early',
            label: 'A',
            lives_saved: { point: 1871, lo: 1500, hi: 2240 },
            dollars_saved: { point: 12.3e6, lo: 9e6, hi: 16e6 },
            cost_per_life_saved_usd: 228,
            misinfo_ratio_change: { point: 0, lo: 0, hi: 0 },
          },
        ],
      }),
    )
    setup.setForCurrent('runState', 'done')
    setup.setForCurrent('selectedInterventionIds', ['evac_d03_30min_early'])
    await nextTick()

    // Trigger a new Re-run — the push must capture the previous best
    // before wiping mcRun.
    await setup.onRunMC()

    const hist =
      setup.scenarioStates['la-puente-hills-m72-ref'].mcRunHistory ?? []
    expect(hist.length).toBe(1)
    expect(hist[0].lives).toBe(1871)
    expect(hist[0].label).toBe('A')
    expect(hist[0].cpls).toBe(228)
    expect(hist[0].ids).toEqual(['evac_d03_30min_early'])
  })

  test('U6: mcRunHistory keeps at most 3 entries; oldest evicted FIFO', async () => {
    const { setup } = await mountView()
    // Each call pushes one entry; after 4, only the 3 most recent remain.
    for (let i = 0; i < 4; i++) {
      // Reset the state-before pieces so each onRunMC sees fresh deltas.
      setup.setForCurrent(
        'mcRun',
        makeMcRun({
          deltas: [
            {
              intervention_id: 'evac_d03_30min_early',
              label: `Round ${i}`,
              lives_saved: { point: 100 + i, lo: 80 + i, hi: 120 + i },
              dollars_saved: { point: 1e6, lo: 0.8e6, hi: 1.2e6 },
              cost_per_life_saved_usd: 100 + i,
              misinfo_ratio_change: { point: 0, lo: 0, hi: 0 },
            },
          ],
        }),
      )
      setup.setForCurrent('runState', 'done')
      setup.setForCurrent('selectedInterventionIds', ['evac_d03_30min_early'])
      await nextTick()
      await setup.onRunMC()
      // After onRunMC the state is wiped; flush any pending micro-tasks.
      await flushPromises()
    }

    const hist =
      setup.scenarioStates['la-puente-hills-m72-ref'].mcRunHistory ?? []
    expect(hist.length).toBe(3)
    // FIFO: newest first; the oldest "Round 0" must have been evicted.
    const labels = hist.map((h) => h.label)
    expect(labels).toEqual(['Round 3', 'Round 2', 'Round 1'])
  })
})

// ---------------------------------------------------------------------------
// M-4 — Re-run with 0 selected does nothing (no network call)
// ---------------------------------------------------------------------------
describe('Phase 2b — misuse: rerun gating', () => {
  test('M-4: clicking Re-run with 0 selected fires no network request', async () => {
    const { wrapper, setup } = await mountView()
    const { auroraApi } = await import('@/api/aurora')
    auroraApi.runMCStreaming.mockClear()

    setup.currentAct = 2
    setup.setForCurrent('mcRun', makeMcRun())
    setup.setForCurrent('runState', 'done')
    setup.setForCurrent('proposedInterventions', makeProposals())
    setup.setForCurrent('selectedInterventionIds', [])
    await nextTick()

    const btn = wrapper.find('.rerun-button')
    expect(btn.exists()).toBe(true)
    expect(btn.element.disabled).toBe(true)
    // Programmatically dispatch a click to bypass any UA disabled-skip.
    btn.element.dispatchEvent(new Event('click', { bubbles: true }))
    await flushPromises()

    expect(auroraApi.runMCStreaming).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// M-5 — 5 fast Re-run clicks → 1 backend POST
// ---------------------------------------------------------------------------
describe('Phase 2b — misuse: rapid click dedupe', () => {
  test('M-5: 5 rapid Re-run clicks dedupe to 1 backend POST per controller cycle', async () => {
    const { setup } = await mountView()
    const { auroraApi } = await import('@/api/aurora')
    auroraApi.runMCStreaming.mockClear()
    // Slow the mock so the loading-flag gate stays true between clicks.
    auroraApi.runMCStreaming.mockImplementation(
      () =>
        new Promise((resolve) =>
          setTimeout(
            () =>
              resolve({ data: { run_id: 'mock-run-id', status: 'started' } }),
            50,
          ),
        ),
    )

    setup.currentAct = 2
    setup.setForCurrent('mcRun', makeMcRun())
    setup.setForCurrent('runState', 'done')
    setup.setForCurrent('selectedInterventionIds', ['evac_d03_30min_early'])
    await nextTick()

    // Fire 5 clicks in close succession (no awaits between).
    const promises = []
    for (let i = 0; i < 5; i++) {
      promises.push(setup.onRunMC())
    }
    await Promise.all(promises)
    await flushPromises()

    // The first click flips loading=true; the next 4 hit the early return.
    expect(auroraApi.runMCStreaming).toHaveBeenCalledTimes(1)
  })
})

// ---------------------------------------------------------------------------
// M-6 — "already_running" backend response doesn't wipe state
// ---------------------------------------------------------------------------
describe('Phase 2b — misuse: idempotent backend rejoin', () => {
  test('M-6: backend already_running response leaves mcRun intact', async () => {
    const { setup } = await mountView()
    const { auroraApi } = await import('@/api/aurora')
    // Backend says "already running" — same run_id as currently held.
    auroraApi.runMCStreaming.mockResolvedValue({
      data: { run_id: 'EXISTING-RUN', status: 'already_running' },
    })

    const existingMcRun = makeMcRun()
    setup.setForCurrent('mcRun', existingMcRun)
    setup.setForCurrent('runState', 'done')
    setup.setForCurrent('streamRunId', 'EXISTING-RUN')
    setup.setForCurrent('selectedInterventionIds', ['evac_d03_30min_early'])
    setup.setForCurrent('proposedInterventions', makeProposals())
    await nextTick()

    await setup.onRunMC()
    await flushPromises()

    // The mcRun MUST survive the idempotent-rejoin path.
    expect(setup.mcRun).not.toBeNull()
    expect(setup.mcRun.n_trials).toBe(8)
    // proposedInterventions also survives.
    expect(setup.proposedInterventions).not.toBeNull()
    expect(setup.proposedInterventions.proposals.length).toBeGreaterThan(0)
  })
})
