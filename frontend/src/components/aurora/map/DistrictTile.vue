<!-- SPDX-License-Identifier: Apache-2.0 -->
<template>
  <g data-aurora-district :transform="`translate(${cx}, ${cy})`">
    <!-- Circular puck: light-tinted vellum fill so the basemap shows
         through, dashed stroke for "extent" semantics on light theme.
         Fill + stroke tint with the district's live damage ratio so the
         puck visibly bleeds red as the disaster propagates. -->
    <circle
      :r="radius"
      :fill="tintFill"
      :stroke="tintStroke"
      stroke-width="1.2"
      stroke-dasharray="3 3"
      style="transition: fill 0.4s ease, stroke 0.4s ease;"
    />
    <!-- Damage halo: extra ring that pulses when the district is actively
         taking losses. Invisible until ratio > 0.05. -->
    <circle
      v-if="damageRatio > 0.05"
      :r="radius + 4"
      fill="none"
      :stroke="haloStroke"
      stroke-width="1"
      :opacity="haloOpacity"
      class="district-halo"
      pointer-events="none"
    />
    <!-- District short label below the puck -->
    <text
      :y="radius + 14"
      text-anchor="middle"
      dominant-baseline="middle"
      class="district-label"
    >{{ district.name }}</text>
    <!-- Live death count appears once losses start. -->
    <text
      v-if="liveDeaths > 0"
      :y="-radius - 4"
      text-anchor="middle"
      dominant-baseline="middle"
      class="district-deaths"
    >{{ liveDeaths.toLocaleString() }}</text>
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
const damageByDistrict = inject('damageByDistrict', { value: {} })
const animationHour = inject('animationHour', { value: -1 })

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

const damageRatio = computed(() => {
  return damageByDistrict.value?.[props.district.district_id] ?? 0
})

// Fill: light vellum → translucent red as damage ramps. Anchor on
// var(--ink-0) at low ratio (the existing vellum look) and color-mix
// toward DAMAGE_COLOR as it climbs.
const DAMAGE_COLOR = '#d6322f'

const tintFill = computed(() => {
  const r = damageRatio.value
  if (r <= 0) {
    return 'color-mix(in srgb, var(--ink-0) 4%, transparent)'
  }
  const pct = Math.min(28, Math.round(r * 28))
  return `color-mix(in srgb, ${DAMAGE_COLOR} ${pct}%, transparent)`
})

const tintStroke = computed(() => {
  const r = damageRatio.value
  if (r <= 0) return 'var(--ink-2)'
  // Stroke saturates faster than fill for legibility.
  const pct = Math.min(80, Math.round(r * 80) + 20)
  return `color-mix(in srgb, ${DAMAGE_COLOR} ${pct}%, var(--ink-2))`
})

const haloStroke = computed(() => DAMAGE_COLOR)
const haloOpacity = computed(() => Math.min(0.55, damageRatio.value * 0.9))

// Live death count for this hour, read from the same source the
// damageByDistrict computation uses but with the actual count rather
// than the normalised ratio. SchematicMap doesn't expose the raw
// counts directly — we infer from ratio × population, which is exact
// given the calibration formula (ratio = deaths/pop × 100, capped).
const liveDeaths = computed(() => {
  const pop = props.district.population ?? 0
  if (!pop) return 0
  const r = damageRatio.value
  if (r <= 0) return 0
  return Math.round((r * pop) / 100)
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
.district-deaths {
  font-size: 11px;
  font-weight: 700;
  fill: #d6322f;
  paint-order: stroke;
  stroke: var(--bg-1);
  stroke-width: 3;
  stroke-linejoin: round;
  letter-spacing: 0.02em;
  font-variant-numeric: tabular-nums;
  pointer-events: none;
  user-select: none;
}

/* Subtle pulse on the damage halo so the eye is drawn to active
   districts. Slow enough to feel organic; respects reduced motion. */
@keyframes districtHaloPulse {
  0%   { opacity: 0.55; }
  50%  { opacity: 0.20; }
  100% { opacity: 0.55; }
}
.district-halo {
  animation: districtHaloPulse 1.8s ease-in-out infinite;
  transform-origin: center;
}
@media (prefers-reduced-motion: reduce) {
  .district-halo { animation: none; }
}
</style>
