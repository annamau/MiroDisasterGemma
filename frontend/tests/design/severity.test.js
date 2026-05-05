// SPDX-License-Identifier: Apache-2.0
import { describe, it, expect } from 'vitest'
import { paletteFor, swatch, bins, paletteName, HAZARD_KINDS } from '@/design/severity.js'

describe('N1 — severity palettes', () => {
  it('exposes the four hazard kinds the v3 plan promised', () => {
    expect(HAZARD_KINDS).toEqual(
      expect.arrayContaining(['earthquake', 'flood', 'tornado', 'volcanic']),
    )
    expect(HAZARD_KINDS.length).toBe(4)
  })

  it('USGS-MMI palette has 10 calibrated bins', () => {
    expect(bins('earthquake').length).toBe(10)
    const labels = bins('earthquake').map(b => b.label)
    expect(labels).toEqual(['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X+'])
  })

  it('flood palette uses NOAA-SLOSH-style depth bins', () => {
    expect(paletteName('flood').name).toMatch(/SLOSH/i)
    expect(paletteName('flood').unit).toBe('feet')
    expect(bins('flood').length).toBe(5)
  })

  it('tornado palette uses Fujita-derived wind ramp', () => {
    expect(paletteName('tornado').unit).toBe('EF')
    const labels = bins('tornado').map(b => b.label)
    expect(labels).toEqual(['EF1', 'EF2', 'EF3', 'EF4', 'EF5'])
  })

  it('volcanic palette uses pyroclastic-distance proxy', () => {
    expect(paletteName('volcanic').name).toMatch(/Pyroclastic/i)
    expect(bins('volcanic').length).toBe(5)
  })

  it('swatch() returns highest bin whose threshold ≤ intensity', () => {
    // MMI VII = "very strong" at threshold 7, so intensity 7.4 → mmi-7 token
    expect(swatch('earthquake', 7.4)).toBe('var(--mmi-7)')
    // intensity 8 lands exactly on a threshold → that bin
    expect(swatch('earthquake', 8)).toBe('var(--mmi-8)')
    // 0.5 is below threshold-I; clamps to lowest bin
    expect(swatch('earthquake', 0.5)).toBe('var(--mmi-1)')
    // Way above max → highest bin
    expect(swatch('earthquake', 99)).toBe('var(--mmi-10)')
  })

  it('flood swatch maps depth-feet to the right bin', () => {
    expect(swatch('flood', 1)).toBe('var(--flood-1)')
    expect(swatch('flood', 5)).toBe('var(--flood-2)')   // ≥3, <6
    expect(swatch('flood', 8)).toBe('var(--flood-3)')   // ≥6, <12
    expect(swatch('flood', 25)).toBe('var(--flood-5)')  // ≥21
  })

  it('paletteFor() falls back to earthquake on unknown kind, never crashes', () => {
    expect(paletteFor('alien-invasion').name).toMatch(/Mercalli/i)
    expect(swatch('alien-invasion', 7)).toBe('var(--mmi-7)')
  })
})
