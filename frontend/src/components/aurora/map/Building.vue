<!-- SPDX-License-Identifier: Apache-2.0 -->
<template>
  <circle
    data-aurora-building
    :cx="cx"
    :cy="cy"
    :r="radius"
    :fill="dynamicColor"
    stroke="rgba(255,255,255,0.85)"
    stroke-width="0.5"
    opacity="0.92"
  />
</template>

<script setup>
import { computed, inject } from 'vue'

const props = defineProps({
  building: {
    type: Object,
    required: true,
    // { building_id, lat, lon, hazus_class, district_id, occupants_day }
  },
  radius: {
    type: Number,
    default: 3,
  },
})

const projectFn = inject('project', null)
// Bump-based reactivity: when leaflet pans/zooms, LeafletStage bumps
// projectVersion. Read it inside the computed so cx/cy recompute.
const projectVersion = inject('projectVersion', { value: 0 })

const cx = computed(() => {
  if (!projectFn) return 0
  // touch reactivity dep
  projectVersion.value
  return projectFn(props.building.lat, props.building.lon)[0]
})

const cy = computed(() => {
  if (!projectFn) return 0
  projectVersion.value
  return projectFn(props.building.lat, props.building.lon)[1]
})

// Color mapping by HAZUS structural class (pristine state).
const HAZUS_COLOR = {
  W1:  'var(--el-water)',
  C1L: 'var(--el-earth)',
  C1M: 'var(--el-earth)',
  PC1: 'var(--el-aether)',
}
// Damage-state color: red. Buildings interpolate from pristine → red as
// the district's damage ratio rises toward 1.
const DAMAGE_COLOR = '#d6322f'

// Read the live per-district damage ratio (0..1) injected by SchematicMap.
const damageByDistrict = inject('damageByDistrict', { value: {} })

const dynamicColor = computed(() => {
  const base = HAZUS_COLOR[props.building.hazus_class] ?? 'var(--ink-1)'
  const ratio = damageByDistrict.value?.[props.building.district_id] ?? 0
  if (ratio <= 0) return base
  // Use color-mix to blend from base → DAMAGE_COLOR by ratio.
  // pct: 0 → base, 100 → red. Round to nearest 10 to keep CSS reasonable.
  const pct = Math.min(100, Math.round(ratio * 100 / 10) * 10)
  return `color-mix(in srgb, ${DAMAGE_COLOR} ${pct}%, ${base})`
})
</script>
