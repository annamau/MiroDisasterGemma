<!-- SPDX-License-Identifier: Apache-2.0 -->
<template>
  <div class="schematic-map-wrapper">
    <!-- Empty state when no buildings exist (defensive against undefined too) -->
    <div v-if="(scenario.buildings ?? []).length === 0" data-aurora-empty class="empty-state">
      <span>No buildings to render</span>
    </div>

    <template v-else>
      <!-- H5: LeafletStage owns the basemap + pan/zoom and exposes a
           projector function via `inject('project')` + a version ref.
           The SVG sits inside the slot and re-projects on every pan/zoom. -->
      <LeafletStage
        v-if="cityPoints.length > 0"
        :points="cityPoints"
        :theme="basemapTheme"
      >
        <template #default="{ viewport }">
          <svg
            class="schematic-map"
            :viewBox="`0 0 ${Math.max(viewport.w || 0, 1)} ${Math.max(viewport.h || 0, 1)}`"
            role="img"
            preserveAspectRatio="none"
            :aria-label="`Schematic map of ${scenario.city ?? 'scenario'}`"
          >
            <defs>
              <radialGradient :id="hazardGradId" cx="50%" cy="50%" r="50%">
                <stop offset="0%" :stop-color="hazardColor" stop-opacity="0.32" />
                <stop offset="55%" :stop-color="hazardColor" stop-opacity="0.08" />
                <stop offset="100%" :stop-color="hazardColor" stop-opacity="0" />
              </radialGradient>
            </defs>

            <!-- District pucks first (so buildings sit on top) -->
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

            <!-- Responder icons -->
            <ResponderIcon
              v-for="hospital in scenario.hospitals"
              :key="hospital.hospital_id"
              :facility="{ ...hospital, type: 'hospital' }"
            />
            <ResponderIcon
              v-for="station in scenario.fire_stations"
              :key="station.station_id"
              :facility="{ ...station, type: 'fire_station' }"
            />
            <ResponderIcon
              v-for="shelter in scenario.shelters"
              :key="shelter.shelter_id"
              :facility="{ ...shelter, type: 'shelter' }"
            />
          </svg>
        </template>
      </LeafletStage>
    </template>

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
import DistrictTile from './map/DistrictTile.vue'
import Building from './map/Building.vue'
import ResponderIcon from './map/ResponderIcon.vue'
import LeafletStage from './LeafletStage.vue'

const props = defineProps({
  scenario: {
    type: Object,
    required: true,
  },
  /** 'light' | 'dark' — passed straight to MapBasemap. Defaults light per H-bundle. */
  basemapTheme: { type: String, default: 'light' },
  /** Current playback hour (0..duration_hours). Drives per-hour district color animation. */
  animationHour: { type: Number, default: -1 },
  /** Full MC run object (mcRun). Used to read per-hour deaths_by_district from baseline timeline. */
  mcRun: { type: Object, default: null },
})

const basemapTheme = computed(() => props.basemapTheme)

/**
 * Per-district damage ratio at the current animation hour.
 * Reads from mcRun.baseline.trials[0].timeline[hour].deaths_by_district
 * and divides by district population to get a 0..1 damage scalar.
 */
const damageByDistrict = computed(() => {
  const out = {}
  const r = props.mcRun
  const h = props.animationHour
  if (!r || h < 0) return out
  const baseline = r.baseline
  const trials = baseline?.trials
  if (!trials || trials.length === 0) return out
  // Use trial 0 for animation (representative; could median later).
  const timeline = trials[0]?.timeline ?? []
  const snap = timeline[Math.min(h, timeline.length - 1)]
  if (!snap?.deaths_by_district) return out
  for (const district of (props.scenario.districts ?? [])) {
    const pop = Math.max(1, district.population ?? 1000)
    const deaths = snap.deaths_by_district[district.district_id] ?? 0
    // Damage ratio: 0 = pristine, 1 = catastrophic. Cap at 0.5 so the
    // color saturation doesn't redline for trivial pop fractions.
    out[district.district_id] = Math.min(1, deaths / pop * 50)
  }
  return out
})

provide('damageByDistrict', damageByDistrict)

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

// District puck radius — fixed for now in pixel space; LeafletStage
// reprojects on every pan/zoom so the puck stays anchored to its
// centroid regardless of scale. Clamped to [16, 36].
const districtRadius = computed(() => 28)

// Building dot radius scales inversely with density. Floor bumped from
// 1.8 → 3.0 so dots stay legible on top of CartoDB Positron tiles at
// city zoom (without the basemap they were fine; with streets visible
// the 1.8px specks disappear into the texture).
const buildingRadius = computed(() => {
  const n = (props.scenario.buildings ?? []).length
  if (n <= 60)  return 5.0
  if (n <= 120) return 4.4
  if (n <= 180) return 4.0
  if (n <= 240) return 3.4
  return 3.0
})

const HAZARD_ELEMENT = {
  earthquake: 'earth',
  flood: 'water',
  volcanic: 'fire',
  tornado: 'air',
}

const hazardElement = computed(() => HAZARD_ELEMENT[props.scenario.hazard?.kind] ?? 'aether')
const hazardColor = computed(() => `var(--el-${hazardElement.value})`)
const hazardGradId = computed(() => `hazardGrad-${props.scenario.scenario_id ?? 'sc'}`)

const hazardLabel = computed(() => {
  const h = props.scenario.hazard
  if (!h) return null
  const kind = (h.kind ?? '').replace(/_/g, ' ')
  const mag = h.magnitude ? ` M${h.magnitude}` : ''
  return `${kind}${mag}`.trim()
})
</script>

<style scoped>
.schematic-map-wrapper {
  position: relative;
  background: var(--bg-2);
  border: 1px solid var(--line);
  border-radius: 12px;
  overflow: hidden;
  display: block;
  width: 100%;
  height: 100%;
}

.schematic-map {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  display: block;
  pointer-events: none;
  overflow: visible;
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
  background: color-mix(in srgb, var(--bg-2) 92%, transparent);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: var(--sp-2) var(--sp-3);
  display: flex;
  flex-direction: column;
  gap: 3px;
  font-size: 11px;
  color: var(--ink-0);
  backdrop-filter: blur(6px);
  box-shadow: 0 4px 14px -6px rgba(26, 34, 56, 0.18);
  pointer-events: none;
  z-index: 2;
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
  top: var(--sp-3);
  left: var(--sp-3);
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--bg-2) 92%, transparent);
  border: 1px solid var(--line);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--ink-0);
  backdrop-filter: blur(6px);
  box-shadow: 0 4px 14px -6px rgba(26, 34, 56, 0.18);
  z-index: 2;
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