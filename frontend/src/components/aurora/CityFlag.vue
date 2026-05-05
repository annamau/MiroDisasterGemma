<!-- SPDX-License-Identifier: Apache-2.0 -->
<template>
  <span class="city-flag" :class="`flag-${size}`" role="img" :aria-label="ariaLabel">
    <component
      :is="iconComponent"
      :size="iconSize"
      :weight="iconWeight"
      :color="iconColor"
    />
    <span v-if="iso" class="iso">{{ iso }}</span>
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { PhFlag, PhPlanet } from '@phosphor-icons/vue'

const props = defineProps({
  /**
   * ISO 3166-1 alpha-2 country code (e.g. "US", "ES", "TR", "IT").
   * Special value "XA" is reserved for the mythological Atlantis scenario;
   * the chip renders a globe glyph instead of a flag and the iso label
   * is replaced with "MYTH".
   */
  iso: { type: String, required: true },
  size: { type: String, default: 'md' }, // 'sm' | 'md' | 'lg'
})

const SIZE_MAP = { sm: 14, md: 18, lg: 22 }
const iconSize = computed(() => SIZE_MAP[props.size] ?? 18)

// Atlantis: mythological — globe glyph, "MYTH" label
const isMyth = computed(() => props.iso?.toUpperCase() === 'XA')

const iconComponent = computed(() => (isMyth.value ? PhPlanet : PhFlag))
const iconWeight = computed(() => (isMyth.value ? 'duotone' : 'fill'))
const iconColor = computed(() =>
  isMyth.value ? 'var(--el-aether)' : 'var(--ink-1)',
)

const ariaLabel = computed(() =>
  isMyth.value ? 'Mythological scenario' : `Country: ${props.iso}`,
)
</script>

<style scoped>
.city-flag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 6px;
  border: 1px solid var(--line);
  background: var(--bg-2);
  border-radius: 4px;
  font-family: var(--ff-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: var(--ink-1);
}
.flag-sm { padding: 1px 4px; font-size: 9px; gap: 3px; }
.flag-lg { padding: 4px 8px; font-size: 12px; gap: 6px; }
.iso { line-height: 1; }
</style>