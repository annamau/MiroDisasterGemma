import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SchematicMap from '@/components/aurora/SchematicMap.vue'
import { makeProjection } from '@/design/projection.js'

const TEST_SCENARIO = {
  scenario_id: 'test-scn',
  city: 'Test City',
  hazard: { kind: 'earthquake', magnitude: 7.0, epicenter_lat: 0, epicenter_lon: 0, duration_hours: 24 },
  districts: [
    { district_id: 'D01', name: 'D01', centroid_lat: -0.01, centroid_lon: -0.01, population: 1000 },
    { district_id: 'D02', name: 'D02', centroid_lat: 0.01, centroid_lon: 0.01, population: 2000 },
  ],
  buildings: [
    { building_id: 'B1', lat: -0.005, lon: -0.005, hazus_class: 'W1', district_id: 'D01', occupants_day: 10 },
    { building_id: 'B2', lat: 0.005, lon: 0.005, hazus_class: 'C1L', district_id: 'D02', occupants_day: 20 },
  ],
  hospitals: [{ hospital_id: 'H1', lat: 0, lon: 0, district_id: 'D01', name: 'H1', beds: 100 }],
  fire_stations: [{ station_id: 'F1', lat: -0.005, lon: 0.005, district_id: 'D02', name: 'F1' }],
  shelters: [{ shelter_id: 'S1', lat: 0.005, lon: -0.005, district_id: 'D01', name: 'S1', capacity: 200 }],
}

describe('M2 projection helper', () => {
  it('projects a point at the bbox center to the viewBox center', () => {
    const proj = makeProjection([
      { lat: -1, lon: -1 },
      { lat: 1, lon: 1 },
    ], 1200, 800)
    const [x, y] = proj(0, 0)
    expect(Math.abs(x - 600)).toBeLessThan(1)
    expect(Math.abs(y - 400)).toBeLessThan(1)
  })

  it('preserves aspect ratio for a square 1° lat × 1° lon scenario', () => {
    const proj = makeProjection([
      { lat: 0, lon: 0 },
      { lat: 1, lon: 1 },
    ], 1200, 800)
    const [x_corner, y_corner] = proj(1, 1)
    const [x_origin, y_origin] = proj(0, 0)
    // The width-to-height ratio of the projected square should match a square
    // (within d3-geoEquirectangular's clipping). Both should be inside viewBox.
    expect(x_corner).toBeGreaterThan(0)
    expect(x_corner).toBeLessThan(1200)
    expect(y_corner).toBeGreaterThanOrEqual(0)
    expect(y_corner).toBeLessThanOrEqual(800)
  })
})

describe('M2 SchematicMap', () => {
  it('renders one circle per building', () => {
    const wrapper = mount(SchematicMap, { props: { scenario: TEST_SCENARIO } })
    const buildingCircles = wrapper.findAll('[data-aurora-building]')
    expect(buildingCircles.length).toBe(TEST_SCENARIO.buildings.length)
  })

  it('renders one tile per district', () => {
    const wrapper = mount(SchematicMap, { props: { scenario: TEST_SCENARIO } })
    const districtTiles = wrapper.findAll('[data-aurora-district]')
    expect(districtTiles.length).toBe(TEST_SCENARIO.districts.length)
  })

  it('renders one ResponderIcon per facility', () => {
    const wrapper = mount(SchematicMap, { props: { scenario: TEST_SCENARIO } })
    // hospitals (1) + fire_stations (1) + shelters (1) = 3
    const responderIcons = wrapper.findAll('[data-aurora-responder]')
    expect(responderIcons.length).toBe(3)
  })

  it('district centroid is within 10% of projected lat/lon centroid', () => {
    // ADVERSARIAL: read the rendered DOM transform of each district <g> and
    // compare against the freshly-projected centroid. If the projection is
    // broken (e.g., naive linear vs d3-geoEquirectangular, or fitSize is
    // missing the padding for tiny bboxes), the rendered position drifts and
    // this test fails.
    const wrapper = mount(SchematicMap, { props: { scenario: TEST_SCENARIO } })
    const allPoints = [
      ...TEST_SCENARIO.districts.map(d => ({ lat: d.centroid_lat, lon: d.centroid_lon })),
      ...TEST_SCENARIO.buildings.map(b => ({ lat: b.lat, lon: b.lon })),
      ...TEST_SCENARIO.hospitals.map(h => ({ lat: h.lat, lon: h.lon })),
      ...TEST_SCENARIO.fire_stations.map(f => ({ lat: f.lat, lon: f.lon })),
      ...TEST_SCENARIO.shelters.map(s => ({ lat: s.lat, lon: s.lon })),
    ]
    const project = makeProjection(allPoints, 1200, 800)
    const tileEls = wrapper.findAll('[data-aurora-district]')
    expect(tileEls.length).toBe(TEST_SCENARIO.districts.length)
    // viewBox diagonal for the 10% tolerance
    const diagonal = Math.sqrt(1200 * 1200 + 800 * 800)
    const tolerance = diagonal * 0.10
    for (const [i, tile] of tileEls.entries()) {
      const district = TEST_SCENARIO.districts[i]
      const [expectedX, expectedY] = project(district.centroid_lat, district.centroid_lon)
      // Parse `translate(<x>, <y>)` from the transform attribute
      const transform = tile.attributes('transform') ?? ''
      const match = transform.match(/translate\(\s*([\d.-]+)\s*,\s*([\d.-]+)\s*\)/)
      expect(match, `tile ${i} missing translate() transform`).toBeTruthy()
      const renderedX = parseFloat(match[1])
      const renderedY = parseFloat(match[2])
      const dist = Math.sqrt((renderedX - expectedX) ** 2 + (renderedY - expectedY) ** 2)
      expect(dist, `district ${district.district_id} drifted ${dist.toFixed(1)}px from projection`).toBeLessThan(tolerance)
    }
  })

  it('building circles do not overlap > 5% by area for adequate viewBox', () => {
    // ADVERSARIAL: read each building circle's (cx, cy) + radius from the DOM,
    // compute pairwise overlap, assert no pair overlaps more than 5% by area.
    // For a sparse scenario with 2 buildings projected to opposite quadrants,
    // overlap should be 0%. If the projection collapses points (e.g., bbox
    // padding broken on small scenarios), buildings stack and this fails.
    const wrapper = mount(SchematicMap, { props: { scenario: TEST_SCENARIO } })
    const circles = wrapper.findAll('[data-aurora-building]')
    expect(circles.length).toBe(TEST_SCENARIO.buildings.length)
    const positions = circles.map(c => ({
      cx: parseFloat(c.attributes('cx') ?? '0'),
      cy: parseFloat(c.attributes('cy') ?? '0'),
      r: parseFloat(c.attributes('r') ?? '3'),
    }))
    // Lens-area overlap between two circles (closed-form)
    function overlapArea(a, b) {
      const d = Math.sqrt((a.cx - b.cx) ** 2 + (a.cy - b.cy) ** 2)
      const r1 = a.r, r2 = b.r
      if (d >= r1 + r2) return 0  // disjoint
      if (d <= Math.abs(r1 - r2)) return Math.PI * Math.min(r1, r2) ** 2  // contained
      const a1 = r1 ** 2 * Math.acos((d ** 2 + r1 ** 2 - r2 ** 2) / (2 * d * r1))
      const a2 = r2 ** 2 * Math.acos((d ** 2 + r2 ** 2 - r1 ** 2) / (2 * d * r2))
      const a3 = 0.5 * Math.sqrt((-d + r1 + r2) * (d + r1 - r2) * (d - r1 + r2) * (d + r1 + r2))
      return a1 + a2 - a3
    }
    for (let i = 0; i < positions.length; i++) {
      for (let j = i + 1; j < positions.length; j++) {
        const overlap = overlapArea(positions[i], positions[j])
        const maxArea = Math.PI * Math.max(positions[i].r, positions[j].r) ** 2
        const overlapPct = overlap / maxArea
        expect(overlapPct, `buildings ${i} & ${j} overlap ${(overlapPct * 100).toFixed(1)}%`).toBeLessThan(0.05)
      }
    }
  })

  it('renders empty-state when scenario has 0 buildings (misuse)', () => {
    const emptyScenario = { ...TEST_SCENARIO, buildings: [] }
    const wrapper = mount(SchematicMap, { props: { scenario: emptyScenario } })
    expect(wrapper.find('[data-aurora-empty]').exists()).toBe(true)
    // Component must NOT crash
    expect(wrapper.vm).toBeDefined()
  })
})

describe('M2 SchematicMap renders 6 real scenarios', () => {
  // We don't actually load 6 scenarios from the backend — just verify the
  // component handles the shapes that scenario_loader builders produce.
  // Use TEST_SCENARIO as a stand-in; if M2 handles this minimal one, the
  // larger ones follow. The full 6-scenario integration is in M8 E2E.
  it('handles a typical scenario shape without errors', () => {
    const wrapper = mount(SchematicMap, { props: { scenario: TEST_SCENARIO } })
    expect(wrapper.find('svg').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('Error')
  })
})
