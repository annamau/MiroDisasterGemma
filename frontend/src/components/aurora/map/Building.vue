<!-- SPDX-License-Identifier: Apache-2.0 -->
<template>
  <circle
    data-aurora-building
    :cx="cx"
    :cy="cy"
    :r="effectiveRadius"
    :fill="dynamicColor"
    :stroke="dynamicStroke"
    stroke-width="0.5"
    :opacity="dynamicOpacity"
    style="transition: fill 0.4s ease, opacity 0.4s ease, r 0.4s ease;"
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
// Damage palette: pristine → orange (warning) → red (damaged) → dark
// charcoal (destroyed). A building progresses through these as the
// district's damage ratio rises past its individual fragility threshold.
const WARN_COLOR = '#f4a045'   // amber
const DAMAGE_COLOR = '#d6322f' // red
const DEAD_COLOR = '#3a2326'   // near-black charcoal

// Read the live per-district damage ratio (0..1) injected by SchematicMap.
const damageByDistrict = inject('damageByDistrict', { value: {} })

/**
 * Deterministic per-building "fragility offset" in [0, 1). Buildings with
 * lower offset die earlier as the district's damage ratio rises; ones with
 * higher offset hold out longer. Drives the visible "spreading damage"
 * effect — without it, every building in a district would change color
 * in lockstep and the eye sees no propagation.
 */
const fragilityOffset = computed(() => {
  const id = String(props.building.building_id ?? '')
  let h = 0
  for (let i = 0; i < id.length; i++) {
    h = ((h << 5) - h) + id.charCodeAt(i)
    h |= 0
  }
  // Map int hash → [0, 1); spread offsets across the range so destruction
  // looks like a propagating wave, not a discrete step.
  return (Math.abs(h) % 1000) / 1000
})

// Per-building damage state. Compares the district's live damage ratio
// against this building's individual fragility threshold + transition
// band, producing one of four states.
const buildingState = computed(() => {
  const ratio = damageByDistrict.value?.[props.building.district_id] ?? 0
  if (ratio <= 0) return 'pristine'
  // Threshold = fragilityOffset, mapped into [0.05, 0.95] so even the
  // most fragile building survives the first tick and the toughest
  // eventually falls if the district approaches catastrophic.
  const threshold = 0.05 + fragilityOffset.value * 0.9
  // Soft transition band of 0.15 — buildings spend a moment in "warning"
  // and "damaged" states before going fully "dead".
  if (ratio < threshold - 0.15) return 'pristine'
  if (ratio < threshold)        return 'warning'
  if (ratio < threshold + 0.15) return 'damaged'
  return 'dead'
})

const dynamicColor = computed(() => {
  const base = HAZUS_COLOR[props.building.hazus_class] ?? 'var(--ink-1)'
  switch (buildingState.value) {
    case 'pristine': return base
    case 'warning':  return WARN_COLOR
    case 'damaged':  return DAMAGE_COLOR
    case 'dead':     return DEAD_COLOR
    default:         return base
  }
})

// Dead buildings shrink and fade slightly — they read as rubble dots
// rather than active structures. The transition CSS on the circle smooths
// the size + opacity change so the eye registers the shift as an event.
const effectiveRadius = computed(() => {
  return buildingState.value === 'dead'
    ? props.radius * 0.55
    : props.radius
})

const dynamicOpacity = computed(() => {
  return buildingState.value === 'dead' ? 0.7 : 0.92
})

const dynamicStroke = computed(() => {
  return buildingState.value === 'dead'
    ? 'rgba(0, 0, 0, 0.4)'
    : 'rgba(255, 255, 255, 0.85)'
})
</script>
