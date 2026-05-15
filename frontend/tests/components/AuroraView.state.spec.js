// SPDX-License-Identifier: Apache-2.0
//
// Phase 1 — Per-scenario state preservation
// =========================================
// These tests prove the `scenarioStates` shallowReactive map inside
// AuroraView.vue isolates Monte Carlo state per scenario_id. The
// pre-refactor view kept singleton refs for `mcRun`, `loadedScenario`,
// etc., so flipping the city wiped panel data. After Phase 1, every
// scenario gets its own entry in `scenarioStates` and the singleton
// refs become computed getters keyed by `selectedScenarioId`.
//
// The tests reach into the mounted component's exposed setup state
// (via `wrapper.vm.$.setupState`) to inspect `scenarioStates`, call
// `setForCurrent`, and assert that switching scenarios doesn't blow
// away prior runs. They also exercise:
//   - lazy default-shape init for never-seen scenarios
//   - per-scenario useLLM
//   - intervention-id list independence
//   - the `_replayTimers` map self-clearing on scenario navigate-away
//   - the 6-entry cap on scenarioStates
//   - rapid same-id writes coalescing into a single preview fetch
//   - mid-flight preview during scenario switch not corrupting state
//
// All API calls are mocked — no real HTTP fires.

import { describe, it, test, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

// Mock the API module BEFORE importing AuroraView so the mock applies
// to the view's import at module-eval time.
vi.mock('@/api/aurora', () => {
  return {
    auroraApi: {
      listScenarios: vi.fn().mockResolvedValue({
        data: {
          scenarios: [
            { scenario_id: 'la-puente-hills-m72-ref', label: 'LA' },
            { scenario_id: 'valencia-dana-2024', label: 'Valencia' },
            { scenario_id: 'pompeii-79', label: 'Pompeii' },
            { scenario_id: 'joplin-ef5-2011', label: 'Joplin' },
            { scenario_id: 'turkey-syria-m78-2023', label: 'Turkey' },
            { scenario_id: 'atlantis', label: 'Atlantis' },
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
        data: { run_id: 'mock-run-id' },
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

// Import after the mock so the SUT picks up the stubs.
const importView = () => import('@/views/AuroraView.vue')

// Helper to mount AuroraView and return both wrapper and exposed setup state.
async function mountView({ url } = {}) {
  if (url && typeof window !== 'undefined') {
    // happy-dom supports history.replaceState for URL setup
    window.history.replaceState({}, '', url)
  }
  const { default: AuroraView } = await importView()
  const wrapper = mount(AuroraView, {
    attachTo: document.body,
    global: {
      stubs: {
        // Stub heavy child components so the test doesn't depend on
        // their setup. Each stub renders nothing.
        CommandShell: { template: '<div><slot /><slot name="topbar" /><slot name="overlay" /></div>' },
        EventRail: { template: '<div />' },
        ScenarioCard: { template: '<div />' },
        InterventionChip: { template: '<div />' },
        RunButton: { template: '<div />' },
        SkeletonCard: { template: '<div />' },
        MCProgressPanel: { template: '<div />' },
        AgentLogTicker: { template: '<div />' },
        HeroNumber: { template: '<div />' },
        DeltaCard: { template: '<div />' },
        ComparatorTable: { template: '<div />' },
        CumulativeChart: { template: '<div />' },
        SchematicMap: { template: '<div />' },
        Act0Brief: { template: '<div />' },
        Act1CityPick: { template: '<div />' },
      },
    },
  })
  // Wait for onMounted() loadIndex/applyDemoSeed to settle.
  await flushPromises()
  return { wrapper, setup: wrapper.vm.$.setupState }
}

beforeEach(() => {
  // Clean URL between tests so URL flags from one test don't leak.
  if (typeof window !== 'undefined') {
    window.history.replaceState({}, '', '/')
    // happy-dom v20 ships localStorage as a getter that throws in some
    // configs; AuroraView reads `window.localStorage?.getItem('aurora-theme')`
    // on setup, so stub it with a minimal in-memory store.
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
  // happy-dom cleanup: detach any attached wrappers.
  document.body.innerHTML = ''
})

// ---------------------------------------------------------------------------
// U1 — setForCurrent writes to the entry keyed by selectedScenarioId
// ---------------------------------------------------------------------------
describe('Phase 1 — scenarioStates: writes', () => {
  test('U1: setForCurrent writes to the entry keyed by selectedScenarioId', async () => {
    const { setup } = await mountView()
    expect(setup.selectedScenarioId).toBe('la-puente-hills-m72-ref')
    setup.setForCurrent('mcRun', { deaths: 100 })
    expect(setup.scenarioStates['la-puente-hills-m72-ref'].mcRun).toEqual({
      deaths: 100,
    })
  })
})

// ---------------------------------------------------------------------------
// U2 — mcRun is null for a scenario that has never been run
// ---------------------------------------------------------------------------
describe('Phase 1 — scenarioStates: lazy defaults', () => {
  test('U2: mcRun is null for a scenario that has never been run', async () => {
    const { setup } = await mountView()
    setup.selectedScenarioId = 'valencia-dana-2024'
    await nextTick()
    expect(setup.mcRun).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// U3 — Cross-scenario independence
// ---------------------------------------------------------------------------
describe('Phase 1 — scenarioStates: cross-scenario independence', () => {
  test('U3: switching scenario reveals new scenario state without mutating prior', async () => {
    const { setup } = await mountView()
    // Set LA mcRun
    setup.setForCurrent('mcRun', { tag: 'LA-run' })
    expect(setup.mcRun).toEqual({ tag: 'LA-run' })

    // Switch to Valencia, set its mcRun
    setup.selectedScenarioId = 'valencia-dana-2024'
    await nextTick()
    setup.setForCurrent('mcRun', { tag: 'VLC-run' })
    expect(setup.mcRun).toEqual({ tag: 'VLC-run' })

    // Switch back to LA — original payload still intact
    setup.selectedScenarioId = 'la-puente-hills-m72-ref'
    await nextTick()
    expect(setup.mcRun).toEqual({ tag: 'LA-run' })
  })
})

// ---------------------------------------------------------------------------
// U4 — Null write on Valencia doesn't clear LA
// ---------------------------------------------------------------------------
describe('Phase 1 — scenarioStates: null write isolation', () => {
  test('U4: setForCurrent(mcRun, null) on Valencia leaves LA mcRun intact', async () => {
    const { setup } = await mountView()
    setup.setForCurrent('mcRun', { tag: 'LA' })
    setup.selectedScenarioId = 'valencia-dana-2024'
    await nextTick()
    setup.setForCurrent('mcRun', { tag: 'VLC' })
    setup.setForCurrent('mcRun', null)
    expect(setup.mcRun).toBeNull()

    setup.selectedScenarioId = 'la-puente-hills-m72-ref'
    await nextTick()
    expect(setup.mcRun).toEqual({ tag: 'LA' })
  })
})

// ---------------------------------------------------------------------------
// U5 — Unknown id returns safe defaults
// ---------------------------------------------------------------------------
describe('Phase 1 — scenarioStates: unknown id safety', () => {
  test('U5: scenarioStates entries lazy-init with default shape', async () => {
    const { setup } = await mountView()
    setup.selectedScenarioId = 'unknown-scenario-x'
    // Note: we DO NOT await nextTick here. The point is to verify that
    // synchronous reads through the computed getters return safe defaults
    // BEFORE the watch fires onLoadScenario and potentially mutates state.
    // Accessing computeds for a never-seen scenario must NOT throw and
    // must return the spec defaults.
    expect(() => setup.mcRun).not.toThrow()
    expect(setup.mcRun).toBeNull()
    expect(setup.runState).toBe('idle')
    expect(setup.streamRunId).toBeNull()
    expect(setup.recentDecisions).toEqual([])
    expect(setup.proposedInterventions).toBeNull()
    expect(setup.animationHour).toBe(0)
    expect(setup.nTrials).toBe(8)
    expect(setup.nPopulation).toBe(80)
    expect(setup.durationHours).toBe(24)
    expect(setup.useLLM).toBe(false)
    // loadedScenario is intentionally NOT asserted here — the watch on
    // selectedScenarioId will async-fetch a preview for the new id and
    // populate it. M2 covers cross-scenario load isolation explicitly.
  })
})

// ---------------------------------------------------------------------------
// U6 — Intervention selection isolated per scenario
// ---------------------------------------------------------------------------
describe('Phase 1 — scenarioStates: intervention selection', () => {
  test('U6: selectedInterventionIds is independent per scenario', async () => {
    const { setup } = await mountView()
    // LA starts with empty list (per spec step 9).
    expect(setup.selectedInterventionIds).toEqual([])
    setup.toggleIntervention('foo')
    expect(setup.selectedInterventionIds).toEqual(['foo'])

    setup.selectedScenarioId = 'valencia-dana-2024'
    await nextTick()
    expect(setup.selectedInterventionIds).toEqual([])
    setup.toggleIntervention('bar')
    expect(setup.selectedInterventionIds).toEqual(['bar'])

    setup.selectedScenarioId = 'la-puente-hills-m72-ref'
    await nextTick()
    expect(setup.selectedInterventionIds).toEqual(['foo'])
  })
})

// ---------------------------------------------------------------------------
// U7 — useLLM per-scenario isolation
// ---------------------------------------------------------------------------
describe('Phase 1 — scenarioStates: useLLM independence', () => {
  test('U7: useLLM is keyed per scenario', async () => {
    const { setup } = await mountView()
    setup.setForCurrent('useLLM', true)
    expect(setup.useLLM).toBe(true)

    setup.selectedScenarioId = 'valencia-dana-2024'
    await nextTick()
    expect(setup.useLLM).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// U8 — Timer token self-clears on scenario switch
// ---------------------------------------------------------------------------
describe('Phase 1 — replay timer guards', () => {
  test('U8: replay timer self-clears when scenario streamRunId changes', async () => {
    vi.useFakeTimers()
    try {
      const { setup } = await mountView()
      // Prime a fake MC result so startMapReplay can compute its duration.
      setup.setForCurrent('mcRun', { duration_hours: 6 })
      setup.setForCurrent('streamRunId', 'run-A')
      setup.startMapReplay()

      // Confirm a timer was registered for LA.
      expect(setup._replayTimers.has('la-puente-hills-m72-ref')).toBe(true)
      const before = setup._replayTimers.get('la-puente-hills-m72-ref').runId
      expect(before).toBe('run-A')

      // Simulate a *different* run firing on the same scenario — the
      // self-clear guard inside the interval should detect the runId
      // mismatch and clearInterval itself on the next tick.
      setup.setForCurrent('streamRunId', 'run-B')
      vi.advanceTimersByTime(5000) // plenty of ticks
      expect(setup._replayTimers.has('la-puente-hills-m72-ref')).toBe(false)
    } finally {
      vi.useRealTimers()
    }
  })
})

// ---------------------------------------------------------------------------
// U9 — Cap at 6 enforced
// ---------------------------------------------------------------------------
describe('Phase 1 — scenarioStates: cap', () => {
  test('U9: initScenarioState refuses entry 7', async () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    try {
      const { setup } = await mountView()
      // Mounting LA already created one entry. Add 5 more to hit 6.
      const ids = [
        'valencia-dana-2024',
        'pompeii-79',
        'joplin-ef5-2011',
        'turkey-syria-m78-2023',
        'atlantis',
      ]
      for (const id of ids) {
        setup.initScenarioState(id)
      }
      expect(Object.keys(setup.scenarioStates).length).toBe(6)
      // 7th attempt is refused.
      setup.initScenarioState('seventh-scenario')
      expect(Object.keys(setup.scenarioStates).length).toBe(6)
      expect(warnSpy).toHaveBeenCalled()
    } finally {
      warnSpy.mockRestore()
    }
  })
})

// ---------------------------------------------------------------------------
// U10 — Same-scenario writes propagate to computed reads (reactivity proof)
// ---------------------------------------------------------------------------
// This is the regression test for the shallowReactive trap. Pre-fix, the
// computed getter would cache its first read of scenarioStates[id].mcRun
// and never see a nested mutation, leaving `vm.mcRun.tag === 'first'`
// even after a `setForCurrent('mcRun', { tag: 'second' })` write. The
// fix replaces the entry object atomically; that top-level key write
// invalidates the dep and the computed re-evaluates.
//
// If you remove the atomic-replace in setForCurrent and revert to
// `scenarioStates[id][field] = value`, this test MUST fail on the
// second assertion (vm.mcRun.tag stays 'first' or stale).
// ---------------------------------------------------------------------------
describe('Phase 1 — scenarioStates: same-scenario reactivity', () => {
  test('U10: same-scenario write to computed propagates on next read', async () => {
    const { wrapper, setup } = await mountView()
    // LA is the default selectedScenarioId.
    expect(setup.selectedScenarioId).toBe('la-puente-hills-m72-ref')

    setup.setForCurrent('mcRun', { tag: 'first' })
    await nextTick()
    // Read via the computed (which is what the template consumes).
    expect(wrapper.vm.mcRun).toEqual({ tag: 'first' })

    // Second write on the SAME scenario — this is the path that froze
    // pre-fix. The computed read must reflect the new value.
    setup.setForCurrent('mcRun', { tag: 'second' })
    await nextTick()
    expect(wrapper.vm.mcRun).toEqual({ tag: 'second' })

    // A third write to round-trip — exercises the steady-state path
    // where the entry has already been replaced once.
    setup.setForCurrent('mcRun', { tag: 'third' })
    await nextTick()
    expect(wrapper.vm.mcRun).toEqual({ tag: 'third' })
  })

  test('U10b: animationHour writes from startMapReplay propagate per tick', async () => {
    vi.useFakeTimers()
    try {
      const { wrapper, setup } = await mountView()
      // Seed a 6-hour MC result so the replay duration is short.
      setup.setForCurrent('mcRun', { duration_hours: 6 })
      setup.setForCurrent('streamRunId', 'run-A')
      setup.startMapReplay()

      // Replay resets animationHour to 0 first.
      expect(wrapper.vm.animationHour).toBe(0)

      // Advance time enough for at least one tick (tick = 2000ms for
      // duration_hours=6 over 12 wall seconds).
      vi.advanceTimersByTime(2500)
      await nextTick()
      // The computed must reflect the new animationHour the timer wrote
      // through setForId. Pre-fix this would stay at 0 because
      // shallowReactive missed the inner mutation.
      expect(wrapper.vm.animationHour).toBeGreaterThan(0)
    } finally {
      vi.useRealTimers()
    }
  })
})

// ---------------------------------------------------------------------------
// M-1 — Rapid alternating-scenario flips don't corrupt state or over-fetch
// ---------------------------------------------------------------------------
// Reviewer note: the prior M-1 wrote the same value 100x. Vue dedupes
// identical scalar writes natively, so a buggy "no dedupe" implementation
// would still have passed. The adversarial form flips between two
// distinct scenario ids — that forces the watcher to fire on every
// change, and tests that the previewScenario calls coalesce to at most
// one per unique id and that no exception is thrown.
// ---------------------------------------------------------------------------
describe('Phase 1 — misuse: rapid alternating-scenario flips', () => {
  test('M1: rapid LA<->Valencia flipping does not corrupt state or over-fetch', async () => {
    const { setup } = await mountView()
    const { auroraApi } = await import('@/api/aurora')
    // Mount already kicked off the initial onLoadScenario for LA. Clear
    // the counter so we only see the flips below.
    auroraApi.previewScenario.mockClear()

    // 50 flips = 100 assignments alternating LA → Valencia → LA → ...
    let threw = null
    try {
      for (let i = 0; i < 50; i++) {
        setup.selectedScenarioId = 'la-puente-hills-m72-ref'
        setup.selectedScenarioId = 'valencia-dana-2024'
      }
    } catch (e) {
      threw = e
    }
    expect(threw).toBeNull()
    await flushPromises()

    // At most one preview call per unique scenario id — the watch
    // dedupes consecutive identical writes natively, and the
    // `if (!loadedScenario) await onLoadScenario()` guard prevents
    // re-fetching once an entry has its scenario.
    expect(auroraApi.previewScenario.mock.calls.length).toBeLessThanOrEqual(2)

    // Both entries exist and are fully initialised with the default shape.
    const la = setup.scenarioStates['la-puente-hills-m72-ref']
    const vlc = setup.scenarioStates['valencia-dana-2024']
    expect(la).toBeTruthy()
    expect(vlc).toBeTruthy()
    for (const entry of [la, vlc]) {
      // Default shape from initScenarioState.
      expect(entry.mcRun).toBeNull()
      expect(entry.runState).toBe('idle')
      expect(entry.selectedInterventionIds).toEqual([])
      expect(entry.nTrials).toBe(8)
      expect(entry.nPopulation).toBe(80)
      expect(entry.durationHours).toBe(24)
    }
    // No spurious extra entries (the flip only touched 2 ids).
    expect(Object.keys(setup.scenarioStates).length).toBe(2)
  })
})

// ---------------------------------------------------------------------------
// M-2 — Mid-flight preview during scenario switch
// ---------------------------------------------------------------------------
describe('Phase 1 — misuse: mid-flight preview', () => {
  test('M2: mid-flight preview during scenario switch does not corrupt loadedScenario', async () => {
    const { auroraApi } = await import('@/api/aurora')
    // Replace previewScenario with a delayed implementation per id.
    auroraApi.previewScenario.mockImplementation((scenarioId) => {
      const delay = scenarioId === 'la-puente-hills-m72-ref' ? 50 : 5
      return new Promise((resolve) =>
        setTimeout(
          () =>
            resolve({
              data: {
                scenario_id: scenarioId,
                city: scenarioId,
                hazard: { kind: 'earthquake', duration_hours: 24 },
                districts: [],
                buildings: [],
                hospitals: [],
                fire_stations: [],
                shelters: [],
              },
            }),
          delay,
        ),
      )
    })

    const { setup } = await mountView()
    // Trigger LA preview (slow), then switch to Valencia (fast). Wait
    // for both to resolve and verify their states are independent and
    // not cross-contaminated.
    setup.selectedScenarioId = 'la-puente-hills-m72-ref'
    await nextTick()
    setup.selectedScenarioId = 'valencia-dana-2024'
    await new Promise((r) => setTimeout(r, 200))
    await flushPromises()

    const la = setup.scenarioStates['la-puente-hills-m72-ref']
    const vlc = setup.scenarioStates['valencia-dana-2024']

    // Both entries should exist.
    expect(la).toBeTruthy()
    expect(vlc).toBeTruthy()

    // Neither should hold the *other* scenario's city — that would be
    // the corruption mode the red-team flagged.
    if (la.loadedScenario) {
      expect(la.loadedScenario.scenario_id).toBe('la-puente-hills-m72-ref')
    }
    if (vlc.loadedScenario) {
      expect(vlc.loadedScenario.scenario_id).toBe('valencia-dana-2024')
    }
  })
})
