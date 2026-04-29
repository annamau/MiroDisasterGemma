<template>
  <div
    class="scenario-card"
    :class="[`element-${scenario.element}`, { selected, 'not-loaded': !scenario.loaded_in_db }]"
    role="button"
    tabindex="0"
    :aria-pressed="selected"
    :aria-label="`Select ${scenario.label} scenario`"
    @click="emit('select', scenario.scenario_id)"
    @keydown.enter.space.prevent="emit('select', scenario.scenario_id)"
  >
    <div class="card-body">
      <ElementBadge
        class="badge-slot"
        :element="scenario.element || 'aether'"
        :icon="scenario.icon || 'Siren'"
        :size="48"
      />
      <div class="text-col">
        <div class="label">{{ scenario.label }}</div>
        <div class="sub" v-if="scenario.sub">{{ scenario.sub }}</div>
        <span
          class="db-badge"
          :class="scenario.loaded_in_db ? 'ok' : 'off'"
        >
          {{ scenario.loaded_in_db ? 'in DB' : 'not loaded' }}
        </span>
      </div>
    </div>
    <div class="hazard-row" v-if="hazardEntries.length">
      <span
        v-for="[k, v] in hazardEntries"
        :key="k"
        class="hazard-param"
      >
        <span class="param-key">{{ k }}</span>
        <span class="param-val">{{ v }}</span>
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import ElementBadge from './ElementBadge.vue'

const props = defineProps({
  scenario: {
    type: Object,
    required: true,
    // shape: { scenario_id, label, sub, hazard_params, element, icon, loaded_in_db }
  },
  selected: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['select'])

const hazardEntries = computed(() => {
  if (!props.scenario.hazard_params) return []
  return Object.entries(props.scenario.hazard_params).slice(0, 4)
})
</script>

<style scoped>
.scenario-card {
  position: relative;
  background: var(--bg-1);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: var(--sp-4) var(--sp-4);
  cursor: pointer;
  outline: none;
  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease,
    border-color 0.18s ease;
  user-select: none;
}

/* Hover — CSS only, no JS */
.scenario-card:hover {
  transform: translateY(-1px);
}
.element-fire:hover {
  box-shadow: 0 0 0 1px var(--el-fire-glow), 0 0 40px -10px var(--el-fire-glow);
}
.element-water:hover {
  box-shadow: 0 0 0 1px var(--el-water-glow), 0 0 40px -10px var(--el-water-glow);
}
.element-earth:hover {
  box-shadow: 0 0 0 1px var(--el-earth-glow), 0 0 40px -10px var(--el-earth-glow);
}
.element-air:hover {
  box-shadow: 0 0 0 1px var(--el-air-glow), 0 0 40px -10px var(--el-air-glow);
}
.element-aether:hover {
  box-shadow: 0 0 0 1px var(--el-aether-glow), 0 0 40px -10px var(--el-aether-glow);
}

/* Active / selected state — permanent glow */
.scenario-card.selected {
  border-width: 1px;
  border-style: solid;
}
.element-fire.selected {
  border-color: var(--el-fire-glow);
  box-shadow: 0 0 0 1px var(--el-fire-glow), 0 0 40px -10px var(--el-fire-glow);
}
.element-water.selected {
  border-color: var(--el-water-glow);
  box-shadow: 0 0 0 1px var(--el-water-glow), 0 0 40px -10px var(--el-water-glow);
}
.element-earth.selected {
  border-color: var(--el-earth-glow);
  box-shadow: 0 0 0 1px var(--el-earth-glow), 0 0 40px -10px var(--el-earth-glow);
}
.element-air.selected {
  border-color: var(--el-air-glow);
  box-shadow: 0 0 0 1px var(--el-air-glow), 0 0 40px -10px var(--el-air-glow);
}
.element-aether.selected {
  border-color: var(--el-aether-glow);
  box-shadow: 0 0 0 1px var(--el-aether-glow), 0 0 40px -10px var(--el-aether-glow);
}

/* Focus ring for keyboard nav */
.scenario-card:focus-visible {
  outline: 2px solid var(--el-aether);
  outline-offset: 2px;
}

@media (prefers-reduced-motion: reduce) {
  .scenario-card {
    transition: none;
  }
  .scenario-card:hover {
    transform: none;
  }
}

/* Layout */
.card-body {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-3);
}

.badge-slot {
  flex-shrink: 0;
  margin-top: 2px;
}

.text-col {
  flex: 1;
  min-width: 0;
}

.label {
  font-size: var(--fz-16);
  font-weight: 600;
  color: var(--ink-0);
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sub {
  font-size: var(--fz-12);
  color: var(--ink-1);
  margin-top: 2px;
  line-height: 1.4;
}

.db-badge {
  display: inline-block;
  margin-top: var(--sp-1);
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 500;
}
.db-badge.ok {
  background: rgba(51, 192, 255, 0.15);
  color: var(--el-water);
}
.db-badge.off {
  background: rgba(90, 96, 117, 0.2);
  color: var(--ink-2);
}

/* Hazard params row */
.hazard-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2);
  margin-top: var(--sp-3);
  padding-top: var(--sp-3);
  border-top: 1px solid var(--line);
}

.hazard-param {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  font-variant-numeric: tabular-nums;
}

.param-key {
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--ink-2);
  font-weight: 500;
}

.param-val {
  color: var(--ink-1);
  font-weight: 600;
}
</style>
