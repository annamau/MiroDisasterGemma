// SPDX-License-Identifier: Apache-2.0
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { h } from 'vue'
import CommandShell from '@/components/aurora/CommandShell.vue'
import EventRail from '@/components/aurora/EventRail.vue'

describe('F4 — CommandShell layout', () => {
  it('renders all four named slots in the grid regions', () => {
    const w = mount(CommandShell, {
      slots: {
        topbar: () => h('div', { class: 'tt' }, 'Topbar'),
        rail:   () => h('div', { class: 'rr' }, 'Rail'),
        stage:  () => h('div', { class: 'ss' }, 'Stage'),
        drawer: () => h('div', { class: 'dd' }, 'Drawer'),
      },
    })
    expect(w.find('.cmd-topbar .tt').exists()).toBe(true)
    expect(w.find('.cmd-rail .rr').exists()).toBe(true)
    expect(w.find('.cmd-stage .ss').exists()).toBe(true)
    // Drawer is conditional — closed on mount.
    expect(w.find('.cmd-drawer').exists()).toBe(false)
  })

  it('opens drawer when openDrawer(id) is called from rail slot', async () => {
    let openFn = null
    const w = mount(CommandShell, {
      slots: {
        rail: ({ openDrawer }) => {
          openFn = openDrawer
          return h('button', {
            class: 'rail-trigger',
            onClick: () => openDrawer('hazard'),
          }, 'Open')
        },
        drawer: ({ drawerId }) => h('div', { class: 'panel' }, `panel:${drawerId}`),
      },
    })
    await w.find('.rail-trigger').trigger('click')
    expect(w.find('.cmd-drawer').exists()).toBe(true)
    expect(w.find('.panel').text()).toBe('panel:hazard')
  })

  it('closes drawer on close button click', async () => {
    const w = mount(CommandShell, {
      slots: {
        rail: ({ openDrawer }) => h('button', {
          class: 'rt',
          onClick: () => openDrawer('hazard'),
        }, 'Open'),
        drawer: () => h('div', { class: 'panel' }, 'P'),
      },
    })
    await w.find('.rt').trigger('click')
    expect(w.find('.cmd-drawer').exists()).toBe(true)
    await w.find('.drawer-close').trigger('click')
    expect(w.find('.cmd-drawer').exists()).toBe(false)
  })
})

describe('F4 — EventRail', () => {
  const GROUPS = [
    { id: 'hazard',     label: 'Hazard',       stat: 'Quake M7.2',  element: 'earth',  icon: 'WaveSawtooth' },
    { id: 'population', label: 'Population',   stat: '80 agents',   element: 'aether', icon: 'UsersThree' },
    { id: 'responders', label: 'Responders',   stat: '12 hospitals',element: 'water',  icon: 'FirstAidKit' },
    { id: 'inter',      label: 'Interventions',stat: '3 selected',  element: 'air',    icon: 'ShieldCheck' },
  ]

  it('renders one pill per group with its label and stat', () => {
    const w = mount(EventRail, { props: { groups: GROUPS } })
    const pills = w.findAll('.rail-pill')
    expect(pills.length).toBe(4)
    expect(pills[0].find('.pill-label').text()).toBe('Hazard')
    expect(pills[0].find('.pill-stat').text()).toBe('Quake M7.2')
  })

  it('emits "open" with the group id on pill click', async () => {
    const w = mount(EventRail, { props: { groups: GROUPS } })
    await w.findAll('.rail-pill .pill-btn')[1].trigger('click')
    expect(w.emitted('open')).toEqual([['population']])
  })

  it('emits "start" on the start button', async () => {
    const w = mount(EventRail, { props: { groups: GROUPS } })
    await w.find('.start-btn').trigger('click')
    expect(w.emitted('start')).toBeTruthy()
  })

  it('disables the start button when startDisabled', async () => {
    const w = mount(EventRail, { props: { groups: GROUPS, startDisabled: true } })
    expect(w.find('.start-btn').attributes('disabled')).toBeDefined()
    await w.find('.start-btn').trigger('click')
    expect(w.emitted('start')).toBeFalsy()
  })

  it('shows the active accent on the active pill', async () => {
    const w = mount(EventRail, { props: { groups: GROUPS, activeId: 'responders' } })
    const pills = w.findAll('.rail-pill')
    expect(pills[2].classes()).toContain('active')
    expect(pills[0].classes()).not.toContain('active')
  })
})
