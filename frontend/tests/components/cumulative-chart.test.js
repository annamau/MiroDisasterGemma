import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import CumulativeChart from '../../src/components/aurora/CumulativeChart.vue'

const ARMS = [
  {
    intervention_id: 'baseline',
    label: 'Baseline',
    element: 'air',
    cumulative_deaths_mean: [0, 5, 12, 22, 35, 48, 60, 70, 78, 82, 85, 88],
  },
  {
    intervention_id: 'evac_d03_30min_early',
    label: 'Evac 30min Early',
    element: 'earth',
    cumulative_deaths_mean: [0, 3, 8, 14, 22, 30, 38, 44, 49, 53, 56, 58],
  },
  {
    intervention_id: 'preposition_d03_4amb',
    label: 'Pre-position 4 Ambulances',
    element: 'aether',
    cumulative_deaths_mean: [0, 4, 10, 18, 28, 38, 48, 56, 62, 67, 70, 72],
  },
]

describe('CumulativeChart', () => {
  it('renders one <path> per arm', () => {
    const wrapper = mount(CumulativeChart, {
      props: { arms: ARMS, nTrials: 30 },
    })
    const paths = wrapper.findAll('path')
    expect(paths.length).toBe(ARMS.length)
  })

  it('uses var(--el-{element}) as stroke color for each path', () => {
    const wrapper = mount(CumulativeChart, {
      props: { arms: ARMS, nTrials: 30 },
    })
    const paths = wrapper.findAll('path')
    expect(paths[0].attributes('stroke')).toBe('var(--el-air)')
    expect(paths[1].attributes('stroke')).toBe('var(--el-earth)')
    expect(paths[2].attributes('stroke')).toBe('var(--el-aether)')
  })

  it('emits HAZUS-MH 2.1 + Worden 2012 attribution and trial count', () => {
    const wrapper = mount(CumulativeChart, {
      props: { arms: ARMS, nTrials: 42 },
    })
    const footer = wrapper.find('.chart-footer').text()
    expect(footer).toContain('HAZUS-MH 2.1')
    expect(footer).toContain('Worden 2012')
    expect(footer).toContain('42 trials')
    expect(footer).toContain('Cumulative mean')
  })

  it('renders an end-label dot + text per arm', () => {
    const wrapper = mount(CumulativeChart, {
      props: { arms: ARMS, nTrials: 30 },
    })
    const labels = wrapper.findAll('.end-label')
    expect(labels.length).toBe(ARMS.length)
    const labelTexts = wrapper.findAll('.end-label-text').map((t) => t.text())
    expect(labelTexts).toContain('Baseline')
    expect(labelTexts).toContain('Evac 30min Early')
    expect(labelTexts).toContain('Pre-position 4 Ambulances')
  })

  it('handles an empty cumulative series gracefully', () => {
    const wrapper = mount(CumulativeChart, {
      props: {
        arms: [
          { intervention_id: 'x', label: 'X', element: 'aether', cumulative_deaths_mean: [] },
        ],
        nTrials: 10,
      },
    })
    expect(wrapper.find('path').attributes('d')).toBe('')
  })

  it('renders fully visible under prefers-reduced-motion (no fade-out)', async () => {
    // happy-dom matchMedia returns matches=true for any query by default; we
    // need to override it to return matches=true for the reduce query so the
    // component takes its reduced-motion branch (set opacity=1 directly).
    const original = window.matchMedia
    window.matchMedia = (q) => ({
      matches: q.includes('reduce'),
      media: q,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
    })
    try {
      const wrapper = mount(CumulativeChart, {
        props: { arms: ARMS, nTrials: 30 },
      })
      // Wait for onMounted's nextTick + reduce-motion branch to run
      await new Promise((r) => setTimeout(r, 0))
      const grid = wrapper.find('.grid')
      expect(grid.exists()).toBe(true)
      expect(grid.attributes('opacity')).toBe('1')
      const labels = wrapper.findAll('.end-label')
      labels.forEach((l) => {
        expect(l.attributes('opacity')).toBe('1')
      })
    } finally {
      window.matchMedia = original
    }
  })
})
