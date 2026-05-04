<template>
  <circle
    data-aurora-building
    :cx="cx"
    :cy="cy"
    :r="radius"
    :fill="hazusColor"
    opacity="0.85"
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

const cx = computed(() => {
  if (!projectFn) return 0
  return projectFn(props.building.lat, props.building.lon)[0]
})

const cy = computed(() => {
  if (!projectFn) return 0
  return projectFn(props.building.lat, props.building.lon)[1]
})

// Color mapping by HAZUS structural class:
//   W1  (wood frame)          → --el-water   (blue)
//   C1L / C1M (concrete)      → --el-earth   (tan/brown)
//   PC1 (precast concrete)    → --el-aether  (purple)
//   fallback                  → --ink-1      (neutral gray)
const HAZUS_COLOR = {
  W1:  'var(--el-water)',
  C1L: 'var(--el-earth)',
  C1M: 'var(--el-earth)',
  PC1: 'var(--el-aether)',
}

const hazusColor = computed(
  () => HAZUS_COLOR[props.building.hazus_class] ?? 'var(--ink-1)',
)
</script>
