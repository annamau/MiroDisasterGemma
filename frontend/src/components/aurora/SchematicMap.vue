<!-- SPDX-License-Identifier: Apache-2.0 -->
<template>
  <div class="schematic-map-wrapper">
    <!-- Empty state when no buildings exist (defensive against undefined too) -->
    <div v-if="(scenario.buildings ?? []).length === 0" data-aurora-empty class="empty-state">
      <span>No buildings to render</span>
    </div>

    <!-- Main SVG canvas -->
    <svg
      v-else
      :viewBox="`0 0 ${VIEW_W} ${VIEW_H}`"
      :width="VIEW_W"
      :height="VIEW_H"
      class="schematic-map"
      role="img"
      preserveAspectRatio="xMidYMid meet"
      :aria-label="`Schematic map of ${scenario.city ?? 'scenario'}`"
    >
      <defs>
        <radialGradient id="auroraVignette" cx="50%" cy="50%" r="65%">
          <stop offset="0%" stop-color="var(--bg-1)" stop-opacity="1" />
          <stop offset="100%" stop-color="var(--bg-0)" stop-opacity="1" />
        </radialGradient>
        <radialGradient :id="hazardGradId" cx="50%" cy="50%" r="50%">
          <stop offset="0%" :stop-color="hazardColor" stop-opacity="0.45" />
          <stop offset="60%" :stop-color="hazardColor" stop-opacity="0.12" />
          <stop offset="100%" :stop-color="hazardColor" stop-opacity="0" />
        </radialGradient>
      </defs>
      <rect :width="VIEW_W" :height="VIEW_H" fill="url(#auroraVignette)" />

      <!-- Hazard halo: visualizes the seismic / DANA / etc. epicenter so the
           scene has a center of attention even before animation kicks in.
           If the real epicenter is offshore, the halo sits clamped to the
           viewport edge with a chevron arrow pointing toward the real
           position so the geography still reads. -->
      <g v-if="hazardProjected" data-aurora-hazard-halo>
        <circle
          :cx="hazardProjected.x"
          :cy="hazardProjected.y"
          :r="hazardRadius"
          :fill="`url(#${hazardGradId})`"
        />
        <circle
          class="hazard-pulse"
          :cx="hazardProjected.x"
          :cy="hazardProjected.y"
          :r="hazardRadius * 0.35"
          :stroke="hazardColor"
          stroke-width="1.5"
          fill="none"
          opacity="0.75"
        />
        <circle
          class="hazard-pulse hazard-pulse-2"
          :cx="hazardProjected.x"
          :cy="hazardProjected.y"
          :r="hazardRadius * 0.55"
          :stroke="hazardColor"
          stroke-width="1"
          fill="none"
          opacity="0.45"
        />

        <!-- Off-screen arrow when the real epicenter sits outside the city bbox -->
        <g v-if="offscreenArrow"
           :transform="`translate(${offscreenArrow.x}, ${offscreenArrow.y}) rotate(${offscreenArrow.deg})`"
        >
          <polygon
            points="14,0 -6,-7 -2,0 -6,7"
            :fill="hazardColor"
            opacity="0.85"
          />
        </g>
      </g>

      <!-- District pucks (render first so buildings sit on top) -->
      <DistrictTile
        v-for="district in scenario.districts"
        :key="district.district_id"
        :district="district"
        :radius="districtRadius"
      />

      <!-- Building dots -->
      <Building
        v-for="building in scenario.buildings"
        :key="building.building_id"
        :building="building"
        :radius="buildingRadius"
      />

      <!-- Responder icons: hospitals -->
      <ResponderIcon
        v-for="hospital in scenario.hospitals"
        :key="hospital.hospital_id"
        :facility="{ ...hospital, type: 'hospital' }"
      />

      <!-- Responder icons: fire stations -->
      <ResponderIcon
        v-for="station in scenario.fire_stations"
        :key="station.station_id"
        :facility="{ ...station, type: 'fire_station' }"
      />

      <!-- Responder icons: shelters -->
      <ResponderIcon
        v-for="shelter in scenario.shelters"
        :key="shelter.shelter_id"
        :facility="{ ...shelter, type: 'shelter' }"
      />
    </svg>

    <!-- Legend overlay -->
    <div v-if="(scenario.buildings ?? []).length > 0" class="legend">
      <div class="legend-row"><span class="dot dot-water"></span><span>Wood frame</span></div>
      <div class="legend-row"><span class="dot dot-earth"></span><span>Concrete</span></div>
      <div class="legend-row"><span class="dot dot-aether"></span><span>Precast</span></div>
      <div class="legend-divider"></div>
      <div class="legend-row"><span class="ic ic-air">+</span><span>Hospital</span></div>
      <div class="legend-row"><span class="ic ic-fire">!</span><span>Fire / EMS</span></div>
      <div class="legend-row"><span class="ic ic-aether">⌂</span><span>Shelter</span></div>
    </div>

    <!-- Hazard tag overlay (top-right) -->
    <div v-if="hazardLabel" class="hazard-tag" :class="`tag-${hazardElement}`">
      <span class="tag-dot"></span>
      <span>{{ hazardLabel }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed, provide } from 'vue'
import { clampToBox, makeProjection, medianNearestRadius } from '@/design/projection.js'
import DistrictTile from './map/DistrictTile.vue'
import Building from './map/Building.vue'
import ResponderIcon from './map/ResponderIcon.vue'

const props = defineProps({
  scenario: {
    type: Object,
    required: true,
  },
})

const VIEW_W = 1200
const VIEW_H = 720

/**
 * Fit the projection to CITY assets only (districts + buildings + facilities).
 * If we include the hazard epicenter — which can be offshore (Valencia DANA)
 * or on a fault line dozens of km from town — the bbox stretches and the
 * city compresses into a corner. The hazard halo is projected separately
 * and clamped via clampToBox so it stays visible without dragging the
 * city out of frame.
 */
const cityPoints = computed(() => {
  const points = []
  for (const d of props.scenario.districts ?? []) {
    points.push({ lat: d.centroid_lat, lon: d.centroid_lon })
  }
  for (const b of props.scenario.buildings ?? []) {
    points.push({ lat: b.lat, lon: b.lon })
  }
  for (const h of props.scenario.hospitals ?? []) {
    points.push({ lat: h.lat, lon: h.lon })
  }
  for (const f of props.scenario.fire_stations ?? []) {
    points.push({ lat: f.lat, lon: f.lon })
  }
  for (const s of props.scenario.shelters ?? []) {
    points.push({ lat: s.lat, lon: s.lon })
  }
  return points
})

const projectFn = computed(() => makeProjection(cityPoints.value, VIEW_W, VIEW_H))

provide('project', (...args) => projectFn.value(...args))

// District puck radius is derived from the nearest-neighbor distance among
// projected district centroids — guarantees no two pucks overlap. Clamped
// to [20, 56] so we don't get cartoon-big single-district scenarios or
// invisibly-small dense ones.
const districtRadius = computed(() => {
  const projected = (props.scenario.districts ?? []).map(d =>
    projectFn.value(d.centroid_lat, d.centroid_lon),
  )
  return medianNearestRadius(projected, 20, 56)
})

// Building dot radius scales inversely with density. Sparse maps get
// 3.5px chunky dots, dense ones (256-building LA) get 1.8px. Keeps
// the schematic legible without aggressive overlap.
const buildingRadius = computed(() => {
  const n = (props.scenario.buildings ?? []).length
  if (n <= 60)  return 3.4
  if (n <= 120) return 2.8
  if (n <= 180) return 2.4
  if (n <= 240) return 2.0
  return 1.8
})

const HAZARD_ELEMENT = {
  earthquake: 'earth',
  flood: 'water',
  volcanic: 'fire',
  tornado: 'air',
}

const hazardElement = computed(() => HAZARD_ELEMENT[props.scenario.hazard?.kind] ?? 'aether')
const hazardColor = computed(() => `var(--el-${hazardElement.value})`)

/**
 * Project the hazard epicenter, then clamp to the viewport. If the real
 * epicenter is offshore or otherwise outside the city bbox, we render the
 * halo at the clamped position and an arrow pointing at the off-screen
 * direction so users still understand "the hazard is over there."
 */
const hazardProjected = computed(() => {
  const h = props.scenario.hazard
  if (!h || h.epicenter_lat == null || h.epicenter_lon == null) return null
  const raw = projectFn.value(h.epicenter_lat, h.epicenter_lon)
  return clampToBox(raw, VIEW_W, VIEW_H, 40)
})

// Hazard halo radius: small relative to viewBox so it reads as
// "the source" not "the entire scene". Decoupled from magnitude beyond
// the viewport-relative cap; the live sim's choropleth carries severity.
const hazardRadius = computed(() => {
  const h = props.scenario.hazard
  if (!h) return 90
  // Magnitude scales the halo modestly: M6 → 70, M7.2 → 95, M7.8 → 110.
  if (h.magnitude) {
    return Math.min(140, Math.max(70, 35 + h.magnitude * 9))
  }
  return 95
})

const hazardGradId = computed(() => `hazardGrad-${props.scenario.scenario_id ?? 'sc'}`)

const hazardLabel = computed(() => {
  const h = props.scenario.hazard
  if (!h) return null
  const kind = (h.kind ?? '').replace(/_/g, ' ')
  const mag = h.magnitude ? ` M${h.magnitude}` : ''
  return `${kind}${mag}`.trim()
})

/**
 * Off-screen direction arrow geometry (only when the hazard is clamped).
 * Drawn as a 16px chevron inset 6px from the clamped position, rotated
 * by `theta` so it points toward the real epicenter.
 */
const offscreenArrow = computed(() => {
  const h = hazardProjected.value
  if (!h || !h.clamped) return null
  // Convert theta (atan2 result, 0=east) to CSS rotation degrees.
  const deg = (h.theta * 180) / Math.PI
  return { x: h.x, y: h.y, deg }
})
</script>

<style scoped>
.schematic-map-wrapper {
  position: relative;
  background: var(--bg-1);
  border: 1px solid var(--line);
  border-radius: 12px;
  overflow: hidden;
  display: block;
  width: 100%;
  aspect-ratio: 5 / 3;
  max-width: 1200px;
}

.schematic-map {
  display: block;
  width: 100%;
  height: 100%;
}

.empty-state {
  padding: var(--sp-8) var(--sp-6);
  color: var(--ink-2);
  font-size: var(--fz-14);
  font-style: italic;
  text-align: center;
}

@keyframes hazardPulse {
  0%   { transform: scale(0.85); opacity: 0.7; }
  100% { transform: scale(1.7);  opacity: 0;   }
}
.hazard-pulse {
  transform-origin: center;
  transform-box: fill-box;
  animation: hazardPulse 3.6s ease-out infinite;
}
.hazard-pulse-2 {
  animation-delay: 1.2s;
  animation-duration: 4.4s;
}
@media (prefers-reduced-motion: reduce) {
  .hazard-pulse, .hazard-pulse-2 { animation: none; }
}

.legend {
  position: absolute;
  left: var(--sp-4);
  bottom: var(--sp-4);
  background: color-mix(in srgb, var(--bg-0) 80%, transparent);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: var(--sp-2) var(--sp-3);
  display: flex;
  flex-direction: column;
  gap: 3px;
  font-size: 11px;
  color: var(--ink-1);
  backdrop-filter: blur(6px);
  pointer-events: none;
}
.legend-row {
  display: flex;
  align-items: center;
  gap: 6px;
}
.legend-divider {
  height: 1px;
  background: var(--line);
  margin: 4px 0;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
.dot-water  { background: var(--el-water); }
.dot-earth  { background: var(--el-earth); }
.dot-aether { background: var(--el-aether); }
.ic {
  width: 14px;
  height: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  border-radius: 3px;
}
.ic-air    { color: var(--el-air); }
.ic-fire   { color: var(--el-fire); }
.ic-aether { color: var(--el-aether); }

.hazard-tag {
  position: absolute;
  top: var(--sp-4);
  right: var(--sp-4);
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--bg-0) 80%, transparent);
  border: 1px solid var(--line);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--ink-1);
  backdrop-filter: blur(6px);
}
.tag-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.tag-earth  .tag-dot { background: var(--el-earth); box-shadow: 0 0 8px var(--el-earth); }
.tag-water  .tag-dot { background: var(--el-water); box-shadow: 0 0 8px var(--el-water); }
.tag-fire   .tag-dot { background: var(--el-fire);  box-shadow: 0 0 8px var(--el-fire); }
.tag-air    .tag-dot { background: var(--el-air);   box-shadow: 0 0 8px var(--el-air); }
.tag-aether .tag-dot { background: var(--el-aether);box-shadow: 0 0 8px var(--el-aether); }
</style>