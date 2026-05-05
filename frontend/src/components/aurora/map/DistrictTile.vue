<!-- SPDX-License-Identifier: Apache-2.0 -->
<template>
  <g data-aurora-district :transform="`translate(${cx}, ${cy})`">
    <!-- Circular puck: light-tinted vellum fill so the basemap shows
         through, dashed stroke for "extent" semantics on light theme. -->
    <circle
      :r="radius"
      fill="color-mix(in srgb, var(--ink-0) 4%, transparent)"
      stroke="var(--ink-2)"
      stroke-width="1"
      stroke-dasharray="3 3"
    />
    <!-- District short label below the puck -->
    <text
      :y="radius + 14"
      text-anchor="middle"
      dominant-baseline="middle"
      class="district-label"
    >{{ district.name }}</text>
  </g>
</template>

<script setup>
import { computed, inject } from 'vue'

const props = defineProps({
  district: {
    type: Object,
    required: true,
    // { district_id, name, centroid_lat, centroid_lon, population }
  },
  radius: {
    type: Number,
    default: 50,
  },
})

// Prefer inject from SchematicMap; fall back to a prop if not provided.
const projectFn = inject('project', null)
const projectVersion = inject('projectVersion', { value: 0 })

const cx = computed(() => {
  if (!projectFn) return 0
  projectVersion.value
  return projectFn(props.district.centroid_lat, props.district.centroid_lon)[0]
})

const cy = computed(() => {
  if (!projectFn) return 0
  projectVersion.value
  return projectFn(props.district.centroid_lat, props.district.centroid_lon)[1]
})
</script>

<style scoped>
.district-label {
  font-size: 11px;
  font-weight: 700;
  fill: var(--ink-0);
  paint-order: stroke;
  stroke: var(--bg-1);
  stroke-width: 3;
  stroke-linejoin: round;
  letter-spacing: 0.04em;
  pointer-events: none;
  user-select: none;
}
</style>
