<!-- SPDX-License-Identifier: Apache-2.0 -->
<template>
  <g data-aurora-district :transform="`translate(${cx}, ${cy})`">
    <!-- Circular puck: fill bg-2 at 90% alpha, 1px stroke ink-2 -->
    <circle
      :r="radius"
      fill="color-mix(in srgb, var(--bg-2) 90%, transparent)"
      stroke="var(--ink-2)"
      stroke-width="1"
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

const cx = computed(() => {
  if (!projectFn) return 0
  return projectFn(props.district.centroid_lat, props.district.centroid_lon)[0]
})

const cy = computed(() => {
  if (!projectFn) return 0
  return projectFn(props.district.centroid_lat, props.district.centroid_lon)[1]
})
</script>

<style scoped>
.district-label {
  font-size: 11px;
  font-weight: 600;
  fill: var(--ink-1);
  letter-spacing: 0.04em;
  pointer-events: none;
  user-select: none;
}
</style>
