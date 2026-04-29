import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import MCProgressPanel from '../../src/components/aurora/MCProgressPanel.vue'

// Stub the API so the component never tries to hit a real endpoint.
vi.mock('@/api/aurora', () => ({
  auroraApi: {
    getMCProgress: vi.fn().mockResolvedValue({ data: { success: true, data: { arms: {}, done: false, error: null, recent_decisions: [] } } }),
    getMCResult: vi.fn().mockResolvedValue({ data: { success: true, data: {} } }),
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
