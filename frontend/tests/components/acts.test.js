// SPDX-License-Identifier: Apache-2.0
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import Act0Brief from '@/components/aurora/acts/Act0Brief.vue'
import Act1CityPick from '@/components/aurora/acts/Act1CityPick.vue'

const MOCK_SCENARIOS = [
  { scenario_id: 'la-puente-hills-m72-ref',  label: 'LA M7.2 Puente Hills' },
  { scenario_id: 'valencia-dana-2024',       label: 'Valencia DANA 2024' },
  { scenario_id: 'turkey-syria-m78-2023',    label: 'Türkiye-Syria M7.8' },
  { scenario_id: 'pompeii-79',               label: 'Pompeii 79 AD' },
  { scenario_id: 'joplin-ef5-2011',          label: 'Joplin EF5 2011' },
  { scenario_id: 'atlantis',                 label: 'Atlantis' },
]

describe('N2 — Act 0 Brief', () => {
  it('renders the wordmark, lede with em "before", and CTA', () => {
    const w = mount(Act0Brief)
    expect(w.find('.wordmark').text()).toBe('Aurora')
    // Lede must contain the user-quoted bet, with "before" as the em emphasis
    expect(w.find('.lede em').text()).toMatch(/before/i)
    // CTA reads "Begin briefing"
    expect(w.find('.cta').text()).toMatch(/begin briefing/i)
  })

  it('emits "continue" when CTA clicked', async () => {
    const w = mount(Act0Brief)
    await w.find('.cta').trigger('click')
    expect(w.emitted('continue')).toBeTruthy()
    expect(w.emitted('continue').length).toBe(1)
  })

  it('renders the USGS-MMI scale stripe (10 bands) — primes Act 4 lexicon', () => {
    const w = mount(Act0Brief)
    const bands = w.findAll('.mmi-stripe span')
    expect(bands.length).toBe(10)
  })
})

describe('N2 — Act 1 City pick', () => {
  it('renders exactly 3 primary cards (LA / Valencia / Türkiye) by default', () => {
    const w = mount(Act1CityPick, { props: { scenarios: MOCK_SCENARIOS } })
    const primaryCards = w.findAll('.city-card:not(.extra)')
    expect(primaryCards.length).toBe(3)
    const ids = primaryCards.map(c => c.attributes('data-scenario'))
    expect(ids).toEqual([
      'la-puente-hills-m72-ref',
      'valencia-dana-2024',
      'turkey-syria-m78-2023',
    ])
  })

  it('renders the other 3 scenarios as REF cards behind <details>', () => {
    const w = mount(Act1CityPick, { props: { scenarios: MOCK_SCENARIOS } })
    const extraCards = w.findAll('.city-card.extra')
    expect(extraCards.length).toBe(3)
    const ids = extraCards.map(c => c.attributes('data-scenario')).sort()
    expect(ids).toEqual(['atlantis', 'joplin-ef5-2011', 'pompeii-79'])
  })

  it('emits "select" with the scenario id on card click', async () => {
    const w = mount(Act1CityPick, { props: { scenarios: MOCK_SCENARIOS } })
    await w.find('[data-scenario="la-puente-hills-m72-ref"]').trigger('click')
    expect(w.emitted('select')).toEqual([['la-puente-hills-m72-ref']])
  })

  it('emits "back" when back button clicked', async () => {
    const w = mount(Act1CityPick, { props: { scenarios: MOCK_SCENARIOS } })
    await w.find('.back').trigger('click')
    expect(w.emitted('back')).toBeTruthy()
  })

  it('renders a CityFlag chip per primary card', () => {
    const w = mount(Act1CityPick, { props: { scenarios: MOCK_SCENARIOS } })
    // 3 primary + 3 extra = 6 flags total
    const flags = w.findAll('.city-flag')
    expect(flags.length).toBe(6)
  })
})
