<!-- SPDX-License-Identifier: Apache-2.0 -->
<template>
  <div ref="container" class="leaflet-stage" data-aurora-leaflet-stage>
    <!-- Leaflet renders tiles into this same container.
         The default slot mounts INSIDE Leaflet's overlayPane via a portal,
         but the simpler approach we use here: child SVG sits as a sibling
         and reads the projector function via inject. -->
    <div ref="overlayHost" class="overlay-host">
      <slot :project="project" :version="version" :viewport="viewport" />
    </div>
    <div class="zoom-ctrls" v-if="ready">
      <button @click="zoomIn" aria-label="Zoom in"><PhPlus :size="14" weight="bold" /></button>
      <button @click="zoomOut" aria-label="Zoom out"><PhMinus :size="14" weight="bold" /></button>
      <button @click="recenter" aria-label="Reset view"><PhArrowsIn :size="14" weight="bold" /></button>
    </div>
  </div>
</template>

<script setup>
/**
 * H5: Leaflet stage with pan / zoom + a projector exposed to children.
 *
 * Owns the Leaflet map + tile layer. Exposes:
 *   - `project(lat, lon)` → [x, y] in container pixels (via
 *     `map.latLngToContainerPoint`).
 *   - `version` ref bumped on every `move`/`zoom` so child SVGs that
 *     consume the projector via `inject('project')` re-render.
 *   - `viewport` ref { width, height, version } for absolute-position
 *     overlays that need to know container dimensions.
 *
 * Children can reach the projector either via the slot scope (`v-slot`)
 * or via `inject('project')`. We provide both for flexibility.
 */
import { computed, onBeforeUnmount, onMounted, provide, ref, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { PhArrowsIn, PhMinus, PhPlus } from '@phosphor-icons/vue'

const props = defineProps({
  /** Array of {lat, lon} — used to fit bbox on first paint and reset. */
  points: { type: Array, required: true },
  /** 'light' | 'dark'. Picks Positron / Dark Matter tiles. */
  theme: { type: String, default: 'light' },
})

const container = ref(null)
const overlayHost = ref(null)

let mapInstance = null
let tileLayerInstance = null

const ready = ref(false)
// Bump on every move/zoom so SVG children reproject. Children use
// `inject('project')` + watch `version` to reactively recompute.
const version = ref(0)
const viewport = ref({ w: 0, h: 0, version: 0 })

const TILE_URL = {
  light: 'https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
  dark:  'https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
}
const ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> ' +
  '&copy; <a href="https://carto.com/attributions">CARTO</a>'

function bbox(points) {
  const lats = points.map(p => p.lat)
  const lons = points.map(p => p.lon)
  return {
    sw: [Math.min(...lats), Math.min(...lons)],
    ne: [Math.max(...lats), Math.max(...lons)],
  }
}

function project(lat, lon) {
  if (!mapInstance) return [0, 0]
  const p = mapInstance.latLngToContainerPoint([lat, lon])
  return [p.x, p.y]
}

// Provide the projector function + version ref so SVG children inside
// the slot can render reactively without prop-drilling.
provide('project', project)
provide('projectVersion', version)
provide('projectViewport', viewport)

function bumpVersion() {
  version.value += 1
  if (container.value) {
    viewport.value = {
      w: container.value.clientWidth,
      h: container.value.clientHeight,
      version: version.value,
    }
  }
}

function zoomIn()  { mapInstance?.zoomIn() }
function zoomOut() { mapInstance?.zoomOut() }
function recenter() {
  if (!mapInstance || !props.points || props.points.length === 0) return
  const b = bbox(props.points)
  mapInstance.fitBounds([b.sw, b.ne], { padding: [40, 40], animate: true })
}

function initMap() {
  if (!container.value || !props.points || props.points.length === 0) return
  const b = bbox(props.points)
  mapInstance = L.map(container.value, {
    zoomControl: false,
    attributionControl: true,
    // Enable interaction — H5 brings real map UX.
    dragging: true,
    scrollWheelZoom: true,
    doubleClickZoom: true,
    boxZoom: true,
    keyboard: true,
    touchZoom: true,
    zoomSnap: 0.5,
    zoomDelta: 0.5,
    minZoom: 8,
    maxZoom: 18,
  })
  mapInstance.attributionControl.setPrefix('')
  mapInstance.fitBounds([b.sw, b.ne], { padding: [40, 40], animate: false })
  tileLayerInstance = L.tileLayer(TILE_URL[props.theme] ?? TILE_URL.light, {
    maxZoom: 19,
    attribution: ATTRIBUTION,
    detectRetina: true,
  }).addTo(mapInstance)

  mapInstance.on('move zoom moveend zoomend resize', bumpVersion)
  ready.value = true
  bumpVersion()
}

function reFit() {
  if (!mapInstance || !props.points || props.points.length === 0) return
  const b = bbox(props.points)
  mapInstance.invalidateSize({ animate: false })
  mapInstance.fitBounds([b.sw, b.ne], { padding: [40, 40], animate: false })
}

function swapTheme(next) {
  if (!mapInstance) return
  if (tileLayerInstance) mapInstance.removeLayer(tileLayerInstance)
  tileLayerInstance = L.tileLayer(TILE_URL[next] ?? TILE_URL.light, {
    maxZoom: 19,
    attribution: ATTRIBUTION,
    detectRetina: true,
  }).addTo(mapInstance)
}

onMounted(() => {
  initMap()
  // Seed viewport on next frame in case the container measured 0×0
  // during the synchronous initMap() pass (Vue mount before layout).
  if (typeof requestAnimationFrame !== 'undefined') {
    requestAnimationFrame(() => {
      mapInstance?.invalidateSize({ animate: false })
      bumpVersion()
    })
  }
  if (typeof ResizeObserver !== 'undefined' && container.value) {
    const ro = new ResizeObserver(() => {
      mapInstance?.invalidateSize({ animate: false })
      bumpVersion()
    })
    ro.observe(container.value)
    onBeforeUnmount(() => ro.disconnect())
  }
})

watch(() => props.points, () => reFit(), { deep: true })
watch(() => props.theme, (n) => swapTheme(n))

onBeforeUnmount(() => {
  if (mapInstance) {
    mapInstance.off()
    mapInstance.remove()
    mapInstance = null
  }
})
</script>

<style scoped>
.leaflet-stage {
  position: absolute;
  inset: 0;
  z-index: 0;
}
.overlay-host {
  position: absolute;
  inset: 0;
  z-index: 400;       /* above leaflet tiles, below leaflet controls */
  pointer-events: none;
}
.overlay-host > * { pointer-events: none; }
.overlay-host :deep([data-aurora-clickable]) { pointer-events: auto; }

/* Leaflet attribution: nudge to bottom-right of stage frame, low-key */
.leaflet-stage :deep(.leaflet-control-attribution) {
  background: color-mix(in srgb, var(--bg-1) 86%, transparent);
  color: var(--ink-2);
  font-family: var(--ff-sans);
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px 0 0 0;
}
.leaflet-stage :deep(.leaflet-control-attribution a) {
  color: var(--ink-1);
  text-decoration: underline;
}

/* Custom zoom controls — match topbar aesthetic */
.zoom-ctrls {
  position: absolute;
  top: var(--sp-3);
  right: var(--sp-3);
  display: flex;
  flex-direction: column;
  gap: 4px;
  z-index: 500;
}
.zoom-ctrls button {
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-2);
  border: 1px solid var(--line);
  border-radius: 6px;
  color: var(--ink-1);
  cursor: pointer;
  box-shadow: 0 2px 6px -2px rgba(26, 34, 56, 0.18);
  transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
}
.zoom-ctrls button:hover {
  background: var(--bg-1);
  color: var(--ink-0);
  border-color: var(--ink-2);
}
.zoom-ctrls button:focus-visible {
  outline: 2px solid var(--el-aether);
  outline-offset: 2px;
}
</style>