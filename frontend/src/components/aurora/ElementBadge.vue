<template>
  <span class="element-badge" :style="badgeStyle" :aria-label="`${element} element icon`">
    <component :is="iconComponent" :size="size" :color="elementColor" :weight="iconWeight" />
  </span>
</template>

<script setup>
import { computed } from 'vue'
import {
  PhFlame,
  PhWaveTriangle,
  PhMountains,
  PhWind,
  PhFirstAidKit,
  PhClockClockwise,
  PhBuildings,
  PhChatCircleDots,
  PhUsers,
  PhSiren,
  PhCircleNotch,
  PhArrowRight,
  PhInfo,
  PhCheck,
} from '@phosphor-icons/vue'

const ICON_MAP = {
  Flame: PhFlame,
  WaveTriangle: PhWaveTriangle,
  Mountains: PhMountains,
  Wind: PhWind,
  FirstAidKit: PhFirstAidKit,
  ClockClockwise: PhClockClockwise,
  Buildings: PhBuildings,
  ChatCircleDots: PhChatCircleDots,
  Users: PhUsers,
  Siren: PhSiren,
  CircleNotch: PhCircleNotch,
  ArrowRight: PhArrowRight,
  Info: PhInfo,
  Check: PhCheck,
}

const ELEMENT_COLOR_MAP = {
  fire: 'var(--el-fire)',
  water: 'var(--el-water)',
  earth: 'var(--el-earth)',
  air: 'var(--el-air)',
  aether: 'var(--el-aether)',
}

const props = defineProps({
  element: {
    type: String,
    required: true,
    validator: (v) => ['fire', 'water', 'earth', 'air', 'aether'].includes(v),
  },
  icon: {
    type: String,
    required: true,
  },
  size: {
    type: Number,
    default: 24,
    validator: (v) => [16, 20, 24, 32, 48].includes(v),
  },
})

const elementColor = computed(() => ELEMENT_COLOR_MAP[props.element] ?? 'currentColor')

const iconComponent = computed(() => ICON_MAP[props.icon] ?? PhFlame)

const iconWeight = computed(() => (props.size >= 24 ? 'bold' : 'regular'))

const badgeStyle = computed(() => ({
  color: elementColor.value,
  filter: `drop-shadow(0 0 8px ${elementColor.value})`,
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  flexShrink: 0,
}))
</script>
