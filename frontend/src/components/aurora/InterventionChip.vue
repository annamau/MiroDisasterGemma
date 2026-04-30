<template>
  <label
    class="intervention-chip"
    :class="[
      `element-${intervention.element || 'aether'}`,
      { selected, disabled },
    ]"
    :aria-disabled="disabled"
  >
    <input
      type="checkbox"
      class="chip-checkbox"
      :checked="selected"
      :disabled="disabled"
      :value="intervention.intervention_id"
      @change="!disabled && emit('toggle', intervention.intervention_id)"
    />
    <ElementBadge
      :element="intervention.element || 'aether'"
      :icon="intervention.icon || 'Siren'"
      :size="16"
    />
    <span class="chip-label">{{ intervention.label }}</span>
    <span
      v-if="intervention.kind"
      class="chip-info"
      :title="intervention.kind"
      role="img"
      :aria-label="`Kind: ${intervention.kind}`"
    >
      <PhInfo :size="12" weight="regular" />
    </span>
  </label>
</template>

<script setup>
import { PhInfo } from '@phosphor-icons/vue'
import ElementBadge from './ElementBadge.vue'

const props = defineProps({
  intervention: {
    type: Object,
    required: true,
    // shape: { intervention_id, label, kind, element, icon? }
  },
  selected: {
    type: Boolean,
    default: false,
  },
  disabled: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['toggle'])
</script>

<style scoped>
.intervention-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-2);
  padding: 5px var(--sp-3);
  border-radius: 999px;
  border: 1px solid var(--line);
  background: var(--bg-1);
  cursor: pointer;
  user-select: none;
  font-size: var(--fz-12);
  color: var(--ink-1);
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    box-shadow 0.15s ease,
    color 0.15s ease;
  white-space: nowrap;
}

/* Hide the native checkbox visually but keep it in tab order (sr-only pattern) */
.chip-checkbox {
  position: absolute;
  opacity: 0;
  width: 1px;
  height: 1px;
  margin: -1px;
  padding: 0;
  border: 0;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
}

/* Hover states by element */
.intervention-chip:hover:not(.disabled) {
  background: var(--bg-2);
}
.element-fire:hover:not(.disabled) {
  border-color: var(--el-fire-glow);
  color: var(--ink-0);
}
.element-water:hover:not(.disabled) {
  border-color: var(--el-water-glow);
  color: var(--ink-0);
}
.element-earth:hover:not(.disabled) {
  border-color: var(--el-earth-glow);
  color: var(--ink-0);
}
.element-air:hover:not(.disabled) {
  border-color: var(--el-air-glow);
  color: var(--ink-0);
}
.element-aether:hover:not(.disabled) {
  border-color: var(--el-aether-glow);
  color: var(--ink-0);
}

/* Selected states */
.element-fire.selected {
  border-color: var(--el-fire-glow);
  background: rgba(242, 92, 31, 0.12);
  color: var(--ink-0);
}
.element-water.selected {
  border-color: var(--el-water-glow);
  background: rgba(51, 192, 255, 0.12);
  color: var(--ink-0);
}
.element-earth.selected {
  border-color: var(--el-earth-glow);
  background: rgba(182, 138, 95, 0.12);
  color: var(--ink-0);
}
.element-air.selected {
  border-color: var(--el-air-glow);
  background: rgba(159, 224, 207, 0.12);
  color: var(--ink-0);
}
.element-aether.selected {
  border-color: var(--el-aether-glow);
  background: rgba(197, 128, 240, 0.12);
  color: var(--ink-0);
}

/* Disabled */
.intervention-chip.disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

/* Focus ring (keyboard) — forwarded from checkbox to label via :focus-within */
.intervention-chip:focus-within {
  outline: 2px solid var(--el-aether);
  outline-offset: 2px;
}

@media (prefers-reduced-motion: reduce) {
  .intervention-chip {
    transition: none;
  }
}

.chip-label {
  flex: 1;
  line-height: 1;
}

.chip-info {
  display: inline-flex;
  align-items: center;
  color: var(--ink-2);
  flex-shrink: 0;
  cursor: help;
}
</style>
