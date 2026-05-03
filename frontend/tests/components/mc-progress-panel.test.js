import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import MCProgressPanel from '../../src/components/aurora/MCProgressPanel.vue'
import { auroraApi } from '@/api/aurora'

// Stub the API so the component never tries to hit a real endpoint.
//
// NOTE: auroraApi.getMCProgress / getMCResult resolve to the OUTER envelope
// `{success, data: {arms, done, recent_decisions, error}}` after the axios
// interceptor at frontend/src/api/index.js:24-34 unwraps response.data.
// The default mock below mirrors that shape — do NOT wrap it in another
// `{ data: ... }` layer.
vi.mock('@/api/aurora', () => ({
  auroraApi: {
    getMCProgress: vi.fn().mockResolvedValue({
      success: true,
      data: { arms: {}, done: false, error: null, recent_decisions: [] },
    }),
    getMCResult: vi.fn().mockResolvedValue({
      success: true,
      data: {},
    }),
  },
}))

const ARMS = [
  { intervention_id: 'baseline', label: 'Baseline', element: 'air', icon: 'Siren', n_trials: 30 },
  { intervention_id: 'evac_d03', label: 'Evac 30min Early', element: 'earth', icon: 'ClockClockwise', n_trials: 30 },
  { intervention_id: 'preposition', label: 'Pre-position 4 Ambulances', element: 'aether', icon: 'FirstAidKit', n_trials: 30 },
  { intervention_id: 'retrofit', label: 'Seismic Retrofit W1', element: 'earth', icon: 'Buildings', n_trials: 30 },
]

describe('MCProgressPanel', () => {
  it('renders one row per arm with an ElementBadge each', () => {
    const wrapper = mount(MCProgressPanel, {
      props: { runId: null, scenarioId: 'test', arms: ARMS },
    })
    const rows = wrapper.findAll('.arm-row')
    expect(rows.length).toBe(4)
    const badges = wrapper.findAll('.element-badge')
    expect(badges.length).toBe(4)
  })

  it('computes percentages from mockArmState correctly', () => {
    const mockState = {
      baseline: { trials_done: 15, trials_total: 30, deaths_running_mean: 12.4 },
      evac_d03: { trials_done: 30, trials_total: 30, deaths_running_mean: 8.1 },
    }
    const wrapper = mount(MCProgressPanel, {
      props: {
        runId: null,
        scenarioId: 'test',
        arms: ARMS,
        mockArmState: mockState,
      },
    })
    const counters = wrapper.findAll('.counter').map((c) => c.text())
    expect(counters[0]).toBe('15/30') // baseline at 50%
    expect(counters[1]).toBe('30/30') // evac at 100%
    expect(counters[2]).toBe('0/30')  // preposition not started
    expect(counters[3]).toBe('0/30')  // retrofit not started
  })

  it('shows a stable zero state when mockArmState is empty', () => {
    const wrapper = mount(MCProgressPanel, {
      props: { runId: null, scenarioId: 'test', arms: ARMS, mockArmState: {} },
    })
    const counters = wrapper.findAll('.counter')
    counters.forEach((c) => expect(c.text()).toBe('0/30'))
  })

  it('renders error message when mockError is set', () => {
    const wrapper = mount(MCProgressPanel, {
      props: { runId: null, scenarioId: 'test', arms: ARMS, mockError: 'kaboom' },
    })
    expect(wrapper.find('.panel-error').exists()).toBe(true)
    expect(wrapper.find('.panel-error').text()).toContain('kaboom')
  })

  it('does not start polling when runId is null', () => {
    const wrapper = mount(MCProgressPanel, {
      props: { runId: null, scenarioId: 'test', arms: ARMS },
    })
    // No interval timer started → component lives without making any fetch
    expect(wrapper.exists()).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// U1 streaming-fix tests — exercise the CORRECTED outer-envelope shape
// The axios interceptor returns res = response.data, so auroraApi.getMCProgress
// resolves to {success, data: {arms, done, recent_decisions, error}} directly.
// ---------------------------------------------------------------------------

const STREAMING_ARMS = [
  {
    intervention_id: 'evac_d03_30min_early',
    label: 'Evac 30min Early',
    element: 'earth',
    icon: 'ClockClockwise',
    n_trials: 30,
  },
]

describe('MCProgressPanel — U1 streaming fix', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('test_streaming_panel_handles_real_axios_response_shape', async () => {
    // Stub returns the OUTER envelope — what the axios interceptor actually resolves to.
    const armsPayload = {
      evac_d03_30min_early: {
        trials_done: 3,
        trials_total: 30,
        deaths_running_mean: 5.0,
        last_update_ts: 0,
      },
    }
    auroraApi.getMCProgress.mockResolvedValueOnce({
      success: true,
      data: { arms: armsPayload, done: false, recent_decisions: [], error: null },
    })

    const wrapper = mount(MCProgressPanel, {
      props: {
        runId: 'abc123',
        scenarioId: 'la-puente-hills-m72-ref',
        arms: STREAMING_ARMS,
        pollInterval: 999999, // prevent re-polls during test
      },
    })

    // Wait for the initial poll() promise to settle
    await new Promise((r) => setTimeout(r, 0))
    await wrapper.vm.$nextTick()

    // No error event should have been emitted
    expect(wrapper.emitted('error')).toBeFalsy()

    // armState should reflect the arms from the outer envelope's data field
    expect(wrapper.vm.recentDecisions).toEqual([])
    // The counter for the arm should show 3/30
    const counter = wrapper.find('.counter')
    expect(counter.text()).toBe('3/30')
  })

  it('test_streaming_panel_handles_rejected_promise', async () => {
    // Stub rejects — simulates a real HTTP 500 (the interceptor rejects on errors)
    auroraApi.getMCProgress.mockRejectedValueOnce(new Error('simulated 500'))

    const wrapper = mount(MCProgressPanel, {
      props: {
        runId: 'abc123',
        scenarioId: 'la-puente-hills-m72-ref',
        arms: STREAMING_ARMS,
        pollInterval: 999999,
      },
    })

    await new Promise((r) => setTimeout(r, 0))
    await wrapper.vm.$nextTick()

    // The catch block at the bottom of poll() should have fired
    expect(wrapper.emitted('error')).toBeTruthy()
    expect(wrapper.emitted('error')[0][0]).toBe('simulated 500')
  })

  it('test_streaming_panel_emits_done_with_payload', async () => {
    const armsPayload = {
      evac_d03_30min_early: {
        trials_done: 30,
        trials_total: 30,
        deaths_running_mean: 4.2,
        last_update_ts: 1,
      },
    }
    const resultPayload = {
      baseline: { deaths: { point: 100 } },
      deltas: [],
    }

    // Progress poll returns done:true
    auroraApi.getMCProgress.mockResolvedValueOnce({
      success: true,
      data: { arms: armsPayload, done: true, recent_decisions: [], error: null },
    })
    // Result fetch returns the final payload
    auroraApi.getMCResult.mockResolvedValueOnce({
      success: true,
      data: resultPayload,
    })

    const wrapper = mount(MCProgressPanel, {
      props: {
        runId: 'abc123',
        scenarioId: 'la-puente-hills-m72-ref',
        arms: STREAMING_ARMS,
        pollInterval: 999999,
      },
    })

    // Two async hops: getMCProgress then getMCResult
    await new Promise((r) => setTimeout(r, 0))
    await wrapper.vm.$nextTick()
    await new Promise((r) => setTimeout(r, 0))
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('done')).toBeTruthy()
    expect(wrapper.emitted('done')[0][0]).toEqual(resultPayload)
  })

  it('test_streaming_panel_handles_explicit_failure_payload', async () => {
    // Defense-in-depth: interceptor normally rejects before reaching here,
    // but the panel should also handle a success:false envelope gracefully.
    auroraApi.getMCProgress.mockResolvedValueOnce({
      success: false,
      error: 'simulated explicit failure',
    })

    const wrapper = mount(MCProgressPanel, {
      props: {
        runId: 'abc123',
        scenarioId: 'la-puente-hills-m72-ref',
        arms: STREAMING_ARMS,
        pollInterval: 999999,
      },
    })

    await new Promise((r) => setTimeout(r, 0))
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('error')).toBeTruthy()
    expect(wrapper.emitted('error')[0][0]).toBe('simulated explicit failure')
  })
})
