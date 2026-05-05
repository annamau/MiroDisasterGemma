<!-- SPDX-License-Identifier: Apache-2.0 -->
<template>
  <!-- 16×16 SVG group centered at the projected facility lat/lon -->
  <g
    data-aurora-responder
    :transform="`translate(${cx - 8}, ${cy - 8})`"
    role="img"
    :aria-label="facility.name"
  >
    <component
      :is="iconComponent"
      :size="16"
      :color="iconColor"
      weight="bold"
    />
  </g>
</template>

<script setup>
import { computed, inject } from 'vue'
import { PhFirstAidKit, PhSiren, PhHouse } from '@phosphor-icons/vue'

const props = defineProps({
  facility: {
    type: Object,
    required: true,
    // { lat, lon, type: "hospital" | "fire_station" | "shelter", name }
  },
})

const projectFn = inject('project', null)

const cx = computed(() => {
  if (!projectFn) return 0
  return projectFn(props.facility.lat, props.facility.lon)[0]
})

const cy = computed(() => {
  if (!projectFn) return 0
  return projectFn(props.facility.lat, props.facility.lon)[1]
})

// Icon selection by facility type
const ICON_MAP = {
  hospital:     PhFirstAidKit,
  fire_station: PhSiren,
  shelter:      PhHouse,
}

// Color selection by facility type
const COLOR_MAP = {
  hospital:     'var(--el-air)',
  fire_station: 'var(--el-fire)',
  shelter:      'var(--el-aether)',
}

const iconComponent = computed(
  () => ICON_MAP[props.facility.type] ?? PhFirstAidKit,
)

const iconColor = computed(
  () => COLOR_MAP[props.facility.type] ?? 'var(--ink-1)',
)
</script>
