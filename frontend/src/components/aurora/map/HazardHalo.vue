<!-- SPDX-License-Identifier: Apache-2.0 -->
<!--
  HazardHalo: visible "this is the disaster" overlay anchored at the
  hazard epicenter. Renders different motion grammar per hazard kind:

  - earthquake: 3 concentric shockwave rings expanding outward from the
    epicenter, each phase-shifted so the wavefront looks continuous.
    Each ring fades as it expands. Plus a permanent epicenter dot with
    a slow ground-shake animation.

  - flood:  one inundation ring whose radius GROWS over the replay
    (anchored to animationHour), simulating water spreading. The ring
    is filled translucent blue.

  - volcanic / fire / tornado: defaults to the earthquake shockwave
    look with element-colored rings.

  All hazards get a small persistent epicenter marker so the user knows
  where the disaster originated.
-->
<template>
  <g v-if="cx !== null" class="hazard-halo" data-aurora-hazard-halo>
    <!-- Persistent epicenter marker (always visible) -->
    <circle
      :cx="cx"
      :cy="cy"
      :r="6"
      :fill="elementColor"
      :stroke="elementColor"
      stroke-width="2"
      opacity="0.95"
      class="epicenter-dot"
    />
    <circle
      :cx="cx"
      :cy="cy"
      :r="3"
      fill="var(--bg-1)"
      opacity="0.9"
    />

    <!-- Off-canvas direction arrow: shown when the real epicenter is
         off the viewport, pointing toward where it actually is. -->
    <g
      v-if="directionAngle !== null"
      :transform="`translate(${cx}, ${cy}) rotate(${directionAngle})`"
    >
      <polygon
        points="14,0 4,-5 4,5"
        :fill="elementColor"
        opacity="0.92"
        class="off-canvas-arrow"
      />
    </g>

    <!-- Flood: a single growing inundation ring that scales with the
         simulation hour. Soft fill so it doesn't drown the buildings. -->
    <template v-if="kind === 'flood'">
      <circle
        :cx="cx"
        :cy="cy"
        :r="floodRadius"
        :fill="elementColor"
        fill-opacity="0.10"
        :stroke="elementColor"
        stroke-width="1.4"
        stroke-opacity="0.55"
        style="transition: r 0.5s ease-out;"
        pointer-events="none"
      />
    </template>

    <!-- Earthquake / default: 3 phase-shifted shockwave rings.
         Each is a <circle> with a CSS animation that grows r via a
         scaling transform. We use a transform-origin trick via
         transform-box: fill-box so the scale is anchored on the dot.
         Multiple .ring classes with different animation-delays produce
         the wavefront chain. -->
    <template v-else>
      <circle
        v-for="i in 3"
        :key="i"
        :cx="cx"
        :cy="cy"
        :r="baseRingRadius"
        fill="none"
        :stroke="elementColor"
        stroke-width="2"
        :style="ringStyle(i)"
        class="shockwave-ring"
        pointer-events="none"
      />
    </template>
  </g>
</template>

<script setup>
import { computed, inject } from 'vue'

const props = defineProps({
  hazard: {
    type: Object,
    required: true,
    // { kind, epicenter_lat, epicenter_lon, magnitude, duration_hours }
  },
})

// Inject from LeafletStage (provided by parent SchematicMap chain).
const projectFn = inject('project', null)
const projectVersion = inject('projectVersion', { value: 0 })
const projectViewport = inject('projectViewport', { value: { w: 0, h: 0 } })
const animationHour = inject('animationHour', { value: -1 })
const totalHours = inject('totalHours', { value: 24 })

const HAZARD_ELEMENT = {
  earthquake: 'earth',
  flood: 'water',
  volcanic: 'fire',
  tornado: 'air',
}

const kind = computed(() => props.hazard?.kind ?? 'earthquake')
const elementClass = computed(() => HAZARD_ELEMENT[kind.value] ?? 'aether')
const elementColor = computed(() => `var(--el-${elementClass.value})`)

// Project the epicenter lat/lon to pane-pixel space. Many real-world
// epicenters sit OUTSIDE the city bbox (LA M7.2 Puente Hills sits east
// of East LA; Valencia DANA sits offshore). Without clamping the halo
// renders off-canvas and the user sees nothing. We clamp the projected
// point to the viewport rect with a small inset, so the halo always
// appears at the edge facing the real epicenter — the visual reads as
// "the disaster originated from that direction."
const projected = computed(() => {
  if (!projectFn || !props.hazard) return null
  projectVersion.value
  const lat = props.hazard.epicenter_lat
  const lon = props.hazard.epicenter_lon
  if (typeof lat !== 'number' || typeof lon !== 'number') return null
  return projectFn(lat, lon)
})

const isOffscreen = computed(() => {
  if (!projected.value) return false
  const [x, y] = projected.value
  const w = projectViewport.value?.w ?? 0
  const h = projectViewport.value?.h ?? 0
  if (!w || !h) return false
  return x < 0 || x > w || y < 0 || y > h
})

const clamped = computed(() => {
  if (!projected.value) return null
  const [x, y] = projected.value
  const w = projectViewport.value?.w ?? 0
  const h = projectViewport.value?.h ?? 0
  if (!w || !h) return [x, y]
  // Inset by 40px so the halo dot + first shockwave ring stay visible
  // even at the edge.
  const inset = 40
  return [
    Math.max(inset, Math.min(w - inset, x)),
    Math.max(inset, Math.min(h - inset, y)),
  ]
})

const cx = computed(() => clamped.value?.[0] ?? null)
const cy = computed(() => clamped.value?.[1] ?? null)

// Direction indicator: when the real epicenter is offscreen, render a
// small arrow on the dot pointing toward the actual epicenter.
const directionAngle = computed(() => {
  if (!isOffscreen.value || !projected.value || !clamped.value) return null
  const [tx, ty] = projected.value
  const [cx_, cy_] = clamped.value
  const dx = tx - cx_
  const dy = ty - cy_
  return (Math.atan2(dy, dx) * 180) / Math.PI
})

// Base ring radius — the starting size of each shockwave before its
// CSS animation scales it outward. ~30px gives a visible initial circle
// at city zoom.
const baseRingRadius = computed(() => 30)

/**
 * Compose per-ring inline style. Each ring gets a phase-shifted
 * animation-delay so the three rings produce a continuous wavefront
 * rather than synchronized pulses. The animation itself is defined in
 * the scoped <style> block.
 */
function ringStyle(i) {
  // 3 rings, each 1.2s out of phase across a 3.6s loop.
  const delay = ((i - 1) * 1.2).toFixed(2)
  return {
    transformBox: 'fill-box',
    transformOrigin: 'center',
    animation: `shockwave 3.6s ease-out infinite`,
    animationDelay: `${delay}s`,
  }
}

/**
 * Flood inundation ring radius. Grows from baseRingRadius at h=0 to
 * ~6× that at end-of-simulation. Reads the simulation clock so the
 * water spread tracks the replay rather than wall-clock CSS time.
 */
const floodRadius = computed(() => {
  const h = Math.max(0, animationHour.value)
  const dur = Math.max(1, totalHours.value)
  const progress = Math.min(1, h / dur)
  // 30 → ~210 pixels, easing toward saturation.
  return baseRingRadius.value + progress * 180
})
</script>

<style scoped>
/* Epicenter dot pulses gently to read as "live event". */
@keyframes epicenterPulse {
  0%, 100% { transform: scale(1);   opacity: 1; }
  50%      { transform: scale(1.18); opacity: 0.7; }
}
.epicenter-dot {
  transform-box: fill-box;
  transform-origin: center;
  animation: epicenterPulse 1.6s ease-in-out infinite;
  filter: drop-shadow(0 0 6px currentColor);
}

/* Shockwave: ring scales from 1× to ~5× while fading.  */
@keyframes shockwave {
  0%   { transform: scale(0.6); opacity: 0.85; stroke-width: 2.4; }
  60%  { opacity: 0.45; }
  100% { transform: scale(4.6); opacity: 0;     stroke-width: 0.6; }
}
.shockwave-ring {
  /* The transform anchor is set inline (transform-box / origin)
     because :scoped CSS doesn't reach inline-defined SVG circles
     reliably across browsers. */
  will-change: transform, opacity;
}

/* Off-canvas direction arrow pulses with the epicenter dot. */
.off-canvas-arrow {
  filter: drop-shadow(0 0 4px currentColor);
}

@media (prefers-reduced-motion: reduce) {
  .epicenter-dot,
  .shockwave-ring {
    animation: none;
  }
}
</style>
