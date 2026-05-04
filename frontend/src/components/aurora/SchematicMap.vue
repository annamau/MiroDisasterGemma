<template>
  <div class="schematic-map-wrapper">
    <!-- Empty state when no buildings exist (defensive against undefined too) -->
    <div v-if="(scenario.buildings ?? []).length === 0" data-aurora-empty class="empty-state">
      <span>No buildings to render</span>
    </div>

    <!-- Main SVG canvas -->
    <svg
      v-else
      viewBox="0 0 1200 800"
      width="1200"
      height="800"
      class="schematic-map"
      role="img"
      :aria-label="`Schematic map of ${scenario.city ?? 'scenario'}`"
    >
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
  </div>
</template>

<script setup>
import { computed, provide } from 'vue'
import { makeProjection } from '@/design/projection.js'
import DistrictTile from './map/DistrictTile.vue'
import Building from './map/Building.vue'
import ResponderIcon from './map/ResponderIcon.vue'

const props = defineProps({
  /**
   * Full scenario object from /api/scenario/{id}/load
   * Shape: { scenario_id, city, districts, buildings, hospitals, fire_stations, shelters, ... }
   */
  scenario: {
    type: Object,
    required: true,
  },
})

const VIEW_W = 1200
const VIEW_H = 800

/**
 * Collect ALL geographic points (buildings + facilities + district centroids)
 * to derive a single projection that fits them all.
 */
const allPoints = computed(() => {
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

const projectFn = computed(() => makeProjection(allPoints.value, VIEW_W, VIEW_H))

// Provide the project function via Vue's provide/inject so child components
// (DistrictTile, Building, ResponderIcon) don't need explicit props.
provide('project', (...args) => projectFn.value(...args))

/**
 * District puck radius: fixed at 50px per spec. Child tiles use this as
 * the visual puck radius; building dots will naturally sit inside when
 * the projection maps buildings to the district area.
 */
const districtRadius = 50
</script>

<style scoped>
.schematic-map-wrapper {
  background: var(--bg-1);
  border: 1px solid var(--line);
  border-radius: 10px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.schematic-map {
  display: block;
  width: 100%;
  height: auto;
  max-width: 1200px;
}

.empty-state {
  padding: var(--sp-8) var(--sp-6);
  color: var(--ink-2);
  font-size: var(--fz-14);
  font-style: italic;
  text-align: center;
}
</style>
